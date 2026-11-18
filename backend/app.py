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

# PDF用の標準日本語フォントを登録（追加ファイル不要で文字化けしません）
JP_FONT = "HeiseiKakuGo-W5"
try:
    pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))
except Exception as e:
    print("CID Font error:", e)
    JP_FONT = "Helvetica"

# 写真から読み取った11月14日〜16日の復元用初期データ
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
        save_transactions(RECOVERED_INITIAL_DATA)
        return list(RECOVERED_INITIAL_DATA)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data:
                save_transactions(RECOVERED_INITIAL_DATA)
                return list(RECOVERED_INITIAL_DATA)
            return data
    except Exception:
        return list(RECOVERED_INITIAL_DATA)

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
    save_transactions(txs)
    return {"success": True, "id": new_id, "transaction": tx_dict}

@app.put("/api/transactions/{tx_id}")
def update_transaction(tx_id: str, tx: Transaction):
    txs = load_transactions()
    for i, t in enumerate(txs):
        if t.get("id") == tx_id:
            tx_dict = tx.dict()
            tx_dict["id"] = tx_id
            txs[i] = tx_dict
            save_transactions(txs)
            return {"success": True, "transaction": tx_dict}
    raise HTTPException(status_code=404, detail="Transaction not found")

@app.delete("/api/transactions/{tx_id}")
def delete_transaction(tx_id: str):
    txs = load_transactions()
    new_txs = [t for t in txs if t.get("id") != tx_id]
    save_transactions(new_txs)
    return {"success": True}

@app.post("/api/transactions/sync")
def sync_transactions(client_txs: List[dict]):
    """ブラウザのバックアップデータとサーバーデータを統合して消滅を防ぐAPI"""
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
        save_transactions(merged)
    merged.sort(key=lambda x: (x.get("date", ""), x.get("id", "")), reverse=True)
    return {"success": True, "transactions": merged}

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
    settings[su
