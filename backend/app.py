import os
import json
import uuid
import base64
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
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

JP_FONT = "HeiseiKakuGo-W5"
try:
    pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))
except Exception as e:
    print("CID Font error:", e)
    JP_FONT = "Helvetica"

RECOVERED_INITIAL_DATA = [
    {"id": "rec1114a", "date": "2026-11-14", "type": "expense", "source_type": "purchase", "category": "仕入高", "amount": 734, "payee": "復元データ(編集可)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1114b", "date": "2026-11-14", "type": "expense", "source_type": "purchase", "category": "仕入高", "amount": 328, "payee": "復元データ(編集可)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1114c", "date": "2026-11-14", "type": "expense", "source_type": "purchase", "category": "仕入高", "amount": 3460, "payee": "復元データ(編集可)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1114d", "date": "2026-11-14", "type": "income", "source_type": "store", "category": "売上高", "amount": 23650, "payee": "店舗売上 (現金)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1115a", "date": "2026-11-15", "type": "expense", "source_type": "purchase", "category": "仕入高", "amount": 1107, "payee": "復元データ 100", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1115b", "date": "2026-11-15", "type": "expense", "source_type": "purchase", "category": "仕入高", "amount": 1632, "payee": "復元データ(編集可)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1115c", "date": "2026-11-15", "type": "expense", "source_type": "purchase", "category": "仕入高", "amount": 874, "payee": "復元データ(編集可)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1115d", "date": "2026-11-15", "type": "expense", "source_type": "purchase", "category": "仕入高", "amount": 1057, "payee": "復元データ(編集可)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1115e", "date": "2026-11-15", "type": "income", "source_type": "store", "category": "売上高", "amount": 10400, "payee": "店舗売上 (現金)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1115f", "date": "2026-11-15", "type": "income", "source_type": "store", "category": "売上高", "amount": 3830, "payee": "店舗売上", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1115g", "date": "2026-11-15", "type": "income", "source_type": "store", "category": "売上高", "amount": 4180, "payee": "店舗売上", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1116a", "date": "2026-11-16", "type": "expense", "source_type": "purchase", "category": "消耗品費", "amount": 663, "payee": "復元データ(編集可)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1116b", "date": "2026-11-16", "type": "expense", "source_type": "purchase", "category": "仕入高", "amount": 1672, "payee": "復元データ(編集可)", "description": "", "bank_name": "現金", "receipt_path": ""},
    {"id": "rec1116c", "date": "2026-11-16", "type": "expense", "source_type": "purchase", "category": "仕入高", "amount": 1533, "payee": "復元データ(編集可)", "description": "", "bank_name": "現金", "receipt_path": ""}
]

def load_transactions():
    if not os.path.exists(DATA_FILE):
        save_transactions(RECOVERED_INITIAL_DATA, sync_drive=False)
        return list(RECOVERED_INITIAL_DATA)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data:
                save_transactions(RECOVERED_INITIAL_DATA, sync_drive=False)
                return list(RECOVERED_INITIAL_DATA)
            return data
    except Exception:
        return list(RECOVERED_INITIAL_DATA)

def push_backup_to_drive(transactions):
    if not GAS_WEBHOOK_URL:
        return False
    try:
        res = requests.post(
            GAS_WEBHOOK_URL,
            json={"action": "save_json_backup", "transactions": transactions},
            timeout=20
        )
        return res.ok
    except Exception as e:
        print("Drive JSON backup error:", e)
        return False

def save_transactions(transactions, sync_drive=True):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(transactions, f, ensure_ascii=False, indent=2)
    if sync_drive:
        push_backup_to_drive(transactions)

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
    id: Optional[str] = None
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
    txs.sort(key=lambda x: (x.get("date", ""), x.get("id", "")), reverse=True)
    return txs

@app.post("/api/transactions")
def create_transaction(tx: Transaction):
    txs = load_transactions()
    new_id = tx.id or str(uuid.uuid4())[:8]
    tx_dict = tx.dict()
    tx_dict["id"] = new_id
    txs.append(tx_dict)
    save_transactions(txs, sync_drive=True)
    return {"success": True, "id": new_id, "transaction": tx_dict}

@app.put("/api/transactions/{tx_id}")
def update_transaction(tx_id: str, tx: Transaction):
    txs = load_transactions()
    for i, t in enumerate(txs):
        if t.get("id") == tx_id:
            tx_dict = tx.dict()
            tx_dict["id"] = tx_id
            txs[i] = tx_dict
            save_transactions(txs, sync_drive=True)
            return {"success": True, "transaction": tx_dict}
    raise HTTPException(status_code=404, detail="Transaction not found")

@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: str):
    txs = load_transactions()
    new_txs = [t for t in txs if t.get("id") != tx_id]
    save_transactions(new_txs, sync_drive=True)
    return {"success": True}

@app.post("/api/transactions/sync")
def sync_transactions(client_txs: List[dict]):
    server_txs = load_transactions()
    by_id = {t.get("id"): t for t in server_txs if t.get("id")}
    changed = False
    for ct in client_txs:
        cid = ct.get("id")
        if cid and cid not in by_id:
            by_id[cid] = ct
            changed = True
    merged = list(by_id.values())
    if changed:
        save_transactions(merged, sync_drive=True)
    merged.sort(key=lambda x: (x.get("date", ""), x.get("id", "")), reverse=True)
    return {"success": True, "transactions": merged}

@app.post("/api/backup/drive/save")
def backup_drive_save():
    txs = load_transactions()
    ok = push_backup_to_drive(txs)
    if not ok:
        raise HTTPException(status_code=500, detail="Google Drive backup failed")
    return {"success": True, "count": len(txs)}

@app.post("/api/backup/drive/load")
def backup_drive_load():
    if not GAS_WEBHOOK_URL:
        raise HTTPException(status_code=400, detail="GAS_WEBHOOK_URL is not configured")
    try:
        res = requests.post(
            GAS_WEBHOOK_URL,
            json={"action": "load_json_backup"},
            timeout=20
        )
        data = res.json()
        if not data.get("success"):
            raise HTTPException(status_code=500, detail=data.get("error", "Load failed"))
        drive_txs = data.get("transactions", [])
        if not isinstance(drive_txs, list):
            drive_txs = []
        current_txs = load_transactions()
        by_id = {t.get("id"): t for t in current_txs if t.get("id")}
        for dt in drive_txs:
            if dt.get("id"):
                by_id[dt["id"]] = dt
        merged = list(by_id.values())
        save_transactions(merged, sync_drive=False)
        merged.sort(key=lambda x: (x.get("date", ""), x.get("id", "")), reverse=True)
        return {"success": True, "transactions": merged}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/summary/monthly")
def get_monthly_summary(month: str = Query(...)):
    txs = load_transactions()
    month_txs = [t for t in txs if t.get("date", "").startswith(month)]
    
    total_income = sum(t["amount"] for t in month_txs if t.get("type") == "income")
    total_expense = sum(t["amount"] for t in month_txs if t.get("type") == "expense")
    net_income = total_income - total_expense
    
    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net_income": net_income
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
    tx_date = payload.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    if not file_base64:
        raise HTTPException(status_code=400, detail="No file data provided")
    
    time_str = datetime.now().strftime("%H%M%S")
    ext = os.path.splitext(filename)[1] or ".jpg"
    new_filename = f"receipt_{tx_date}_{time_str}{ext}"
    
    if GAS_WEBHOOK_URL:
        try:
            res = requests.post(
                GAS_WEBHOOK_URL,
                json={"filename": new_filename, "file": file_base64},
                timeout=20
            )
            data = res.json()
            if data.get("success") and data.get("file_url"):
                return {
                    "success": True,
                    "receipt_url": data["file_url"],
                    "filename": new_filename,
                    "storage": "gdrive"
                }
        except Exception as e:
            print("Google Drive upload error:", e)
            
    try:
        file_bytes = base64.b64decode(file_base64)
        file_path = os.path.join(RECEIPTS_DIR, new_filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return {
            "success": True,
            "receipt_url": f"/receipts/{new_filename}",
            "filename": new_filename,
            "storage": "local"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/excel")
def export_excel(month: str = Query(...)):
    txs = [t for t in load_transactions() if t.get("date", "").startswith(month)]
    txs.sort(key=lambda x: x.get("date", ""))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{month} 出納帳"

    headers = ["日付", "区分", "勘定科目", "金額(円)", "取引先・店舗名", "決済手段・口座", "摘要・内訳"]
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")

    for t in txs:
        ws.append([
            t.get("date"),
            "売上" if t.get("type") == "income" else ("支出" if t.get("type") == "expense" else "口座移動"),
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
    txs.sort(key=lambda x: x.get("date", ""))
    
    total_inc = sum(t["amount"] for t in txs if t.get("type") == "income")
    total_exp = sum(t["amount"] for t in txs if t.get("type") == "expense")
    net_inc = total_inc - total_exp

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont(JP_FONT, 16)
    p.drawString(40, height - 45, f"【勘太郎】月次出納帳レポート ({month})")
    
    p.setFont(JP_FONT, 11)
    p.drawString(40, height - 70, f"総売上: ¥{total_inc:,}   |   総支出: ¥{total_exp:,}   |   差引利益: ¥{net_inc:,}")
    p.line(40, height - 78, width - 40, height - 78)

    y = height - 100
    p.setFont(JP_FONT, 10)
    p.drawString(40, y, "日付")
    p.drawString(110, y, "区分")
    p.drawString(155, y, "勘定科目")
    p.drawString(240, y, "金額")
    p.drawString(315, y, "取引先 / 摘要メモ")
    p.line(40, y - 6, width - 40, y - 6)
    
    y -= 22
    p.setFont(JP_FONT, 9)
    for t in txs:
        t_type = "売上" if t.get("type") == "income" else ("支出" if t.get("type") == "expense" else "銀行")
        p.drawString(40, y, str(t.get("date", "")))
        p.drawString(110, y, t_type)
        p.drawString(155, y, str(t.get("category", ""))[:8])
        p.drawString(240, y, f"¥{t.get('amount', 0):,}")
        
        memo = f"{t.get('payee', '')} {t.get('description', '')}".strip()
        p.drawString(315, y, memo[:30])
        
        y -= 18
        if y < 50:
            p.showPage()
            p.setFont(JP_FONT, 9)
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
    txs.sort(key=lambda x: x.get("date", ""))
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
            f"{t.get('payee')} {t.get('description')}".strip()
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
    txs.sort(key=lambda x: x.get("date", ""))
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
            f"{t.get('payee')} {t.get('description')}".strip()
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=Yayoi_{month}.csv"}
    )

@app.get("/api/export/csv/tax")
def export_tax_csv(month: str = Query(...)):
    txs = [t for t in load_transactions() if t.get("date", "").startswith(month)]
    txs.sort(key=lambda x: x.get("date", ""))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日付", "区分", "勘定科目", "金額", "取引先", "決済手段・口座", "摘要・内訳"])
    for t in txs:
        writer.writerow([
            t.get("date"),
            "収入" if t.get("type") == "income" else ("支出" if t.get("type") == "expense" else "口座移動"),
            t.get("category"),
            t.get("amount"),
            t.get("payee"),
            t.get("bank_name"),
            t.get("description")
        ])
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=KakuteiShinkoku_{month}.csv"}
    )

app.mount("/receipts", StaticFiles(directory=RECEIPTS_DIR), name="receipts")

FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
