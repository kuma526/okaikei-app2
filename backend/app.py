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

# Google Apps Script Web App URL (環境変数から取得)
GAS_WEBHOOK_URL = os.environ.get("GAS_WEBHOOK_URL", "")

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
    type: str  # 'income', 'expense', 'bank'
    source_type: str  # 'purchase', 'store', 'uber', 'rocket', etc.
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
    
    if GAS_WEBHOOK_URL:
        try:
            res = requests.post(
                GAS_WEBHOOK_URL,
                json={"filename": filename, "file": file_base64},
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
        ext = os.path.splitext(filename)[1] or ".jpg"
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

app.mount("/receipts", StaticFiles(directory=RECEIPTS_DIR), name="receipts")

# 静的ファイルの配信（フロントエンドおよびassetsパスの解決）
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
