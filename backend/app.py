import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

import reportlab
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import csv
import io
import requests

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "transactions.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
RECEIPTS_DIR = os.path.join(BASE_DIR, "receipts")

os.makedirs(RECEIPTS_DIR, exist_ok=True)

GAS_WEBHOOK_URL = os.environ.get("GAS_WEBHOOK_URL", "")

# ── 日本語フォント（IPAexGothic等）の登録処理 ──
FONT_NAME = "Helvetica" # フォールバック
font_path = os.path.join(BASE_DIR, "ipaexg.ttf")
if os.path.exists(font_path):
    try:
        pdfmetrics.registerFont(TTFont('IPAexGothic', font_path))
        FONT_NAME = 'IPAexGothic'
    except Exception as e:
        print("Font registration error:", e)

def load_transactions():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_transactions(transactions):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(transactions, f, ensure_ascii=False, indent=2)

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {"default_bank_name": "三井住友銀行", "card_fee_rate": "3.24"}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"default_bank_name": "三井住友銀行", "card_fee_rate": "3.24"}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

class Transaction(BaseModel):
    date: str
    type: str
    source_type: str
    category: str
    amount: int
    payee: Optional[str] = ""
    description: Optional[str] = ""
    bank_name: Optional[str] = "現金"
    receipt_path: Optional[str] = ""
    ocr_data: Optional[dict] = None

class SettingUpdate(BaseModel):
    key: str
    value: str

@app.get("/api/transactions")
def get_transactions(month: Optional[str] = None):
    txs = load_transactions()
    if month:
        txs = [t for t in txs if t.get("date", "").startswith(month)]
    txs.sort(key=lambda x: x.get("date", ""), reverse=True)
    return txs

@app.post("/api/transactions")
def create_transaction(tx: Transaction):
    txs = load_transactions()
    new_id = str(uuid.uuid4())[:8]
    tx_dict = tx.dict()
    tx_dict["id"] = new_id
    txs.append(tx_dict)
    save_transactions(txs)
    return {"success": True, "id": new_id}

@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: str):
    txs = load_transactions()
    new_txs = [t for t in txs if t.get("id") != tx_id]
    if len(new_txs) == len(txs):
        raise HTTPException(status_code=404, detail="Transaction not found")
    save_transactions(new_txs)
    return {"success": True}

@app.get("/api/summary/monthly")
def get_monthly_summary(month: str = Query(...)):
    txs = load_transactions()
    month_txs = [t for t in txs if t.get("date", "").startswith(month)]
    
    total_income = sum(t["amount"] for t in month_txs if t.get("type") == "income")
    total_expense = sum(t["amount"] for t in month_txs if t.get("type") == "expense")
    net_income = total_income - total_expense
    
    income_by_source = {
        "store": {"total": sum(t["amount"] for t in month_txs if t.get("source_type") == "store")},
        "uber": {"total": sum(t["amount"] for t in month_txs if t.get("source_type") == "uber")},
        "rocket": {"total": sum(t["amount"] for t in month_txs if t.get("source_type") == "rocket")}
    }
    
    bank_deposits = sum(t["amount"] for t in month_txs if t.get("source_type") == "deposit")
    bank_withdrawals = sum(t["amount"] for t in month_txs if t.get("source_type") == "withdrawal")
    
    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net_income": net_income,
        "income_by_source": income_by_source,
        "bank_deposits": bank_deposits,
        "bank_withdrawals": bank_withdrawals
    }

@app.get("/api/settings")
def get_settings_api():
    return load_settings()

@app.post("/api/settings")
def update_setting(su: SettingUpdate):
    settings = load_settings()
    settings[su.key] = su.value
    save_settings(settings)
    return {"success": True}

@app.post("/api/upload-receipt")
def upload_receipt(payload: dict):
    filename = payload.get("filename", "receipt.jpg")
    file_base64 = payload.get("file", "")
    
    if not file_base64:
        raise HTTPException(status_code=400, detail="No file data provided")
    
    # 日付付きファイル名へのリネーム処理
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(filename)[1] or ".jpg"
    new_filename = f"receipt_{date_str}{ext}"
    
    if GAS_WEBHOOK_URL:
        try:
            res = requests.post(
                GAS_WEBHOOK_URL,
                json={"filename": new_filename, "file": file_base64},
                timeout=15
            )
            data = res.json()
            if data.get("success") and data.get("file_url"):
                return {
                    "success": True,
                    "receipt_url": data["file_url"],
                    "storage": "gdrive"
                }
        except Exception as e:
            print("Google Drive upload error:", e)
            
    try:
        import base64
        file_bytes = base64.b64decode(file_base64)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(RECEIPTS_DIR, unique_name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return {
            "success": True,
            "receipt_url": f"/receipts/{unique_name}",
            "storage": "local"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/excel")
def export_excel(month: str = Query(...)):
    txs = [t for t in load_transactions() if t.get("date", "").startswith(month)]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{month} 出納帳"

    headers = ["日付", "種別", "勘定科目", "金額", "取引先", "決済・口座", "摘要"]
    ws.append(headers)

    for t in txs:
        ws.append([
            t.get("date"),
            "収入" if t.get("type") == "income" else ("支出" if t.get("type") == "expense" else "銀行移動"),
            t.get("category"),
            t.get("amount"),
            t.get("payee"),
            t.get("bank_name"),
            t.get("description")
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"Kaikei_{month}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )

@app.get("/api/export/pdf")
def export_pdf(month: str = Query(...)):
    txs = [t for t in load_transactions() if t.get("date", "").startswith(month)]
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont(FONT_NAME, 14)
    p.drawString(50, height - 50, f"【勘太郎】月次レポート ({month})")
    
    p.setFont(FONT_NAME, 10)
    y = height - 90
    for t in txs:
        line = f"{t.get('date')} | {t.get('category')} | ¥{t.get('amount'):,} | {t.get('payee', '')}"
        p.drawString(50, y, line)
        y = y - 20
        if y < 50:
            p.showPage()
            p.setFont(FONT_NAME, 10)
            y = height - 50

    p.save()
    buffer.seek(0)
    filename = f"Report_{month}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )

@app.get("/api/export/csv/mf")
def export_mf_csv(month: str = Query(...)):
    txs = [t for t in load_transactions() if t.get("date", "").startswith(month)]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["計算期間", "日付", "借方勘定科目", "借方金額", "貸方勘定科目", "貸方金額", "摘要"])
    for t in txs:
        is_inc = t.get("type") == "income"
        writer.writerow([
            t.get("date"),
            t.get("date"),
            t.get("bank_name") if is_inc else t.get("category"),
            t.get("amount"),
            t.get("category") if is_inc else t.get("bank_name"),
            t.get("amount"),
            f"{t.get('payee')} {t.get('description')}"
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=MF_{month}.csv"}
    )

@app.get("/api/export/csv/yayoi")
def export_yayoi_csv(month: str = Query(...)):
    txs = [t for t in load_transactions() if t.get("date", "").startswith(month)]
    output = io.StringIO()
    writer = csv.writer(output)
    for t in txs:
        is_inc = t.get("type") == "income"
        writer.writerow([
            2100,
            t.get("date"),
            t.get("bank_name") if is_inc else t.get("category"),
            "",
            t.get("category") if is_inc else t.get("bank_name"),
            "",
            t.get("amount"),
            t.get("amount"),
            f"{t.get('payee')} {t.get('description')}"
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=Yayoi_{month}.csv"}
    )

app.mount("/receipts", StaticFiles(directory=RECEIPTS_DIR), name="receipts")

FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
