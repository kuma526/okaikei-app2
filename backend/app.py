import os
import io
import uuid
import shutil
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.database import (
    init_db, get_transactions, get_transaction_by_id, create_transaction,
    update_transaction, delete_transaction, get_monthly_summary,
    get_setting, set_setting, get_all_settings, get_db_connection
)
from backend.export_service import export_to_excel, export_to_pdf, export_moneyforward_csv, export_yayoi_csv

# ディレクトリ設定
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "backend", "uploads")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

# アプリ初期化
app = FastAPI(title="個人事業主 出納帳 Webアプリ", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic モデル
class TransactionCreate(BaseModel):
    date: str
    type: str # 'income', 'expense', 'bank'
    source_type: str # 'uber', 'rocket', 'manual_income', 'purchase', 'bank_transfer', 'manual_expense', 'deposit', 'withdrawal'
    category: str # 勘定科目
    amount: int
    payee: Optional[str] = ""
    description: Optional[str] = ""
    bank_name: Optional[str] = "現金"
    receipt_path: Optional[str] = ""
    ocr_data: Optional[Any] = None

class TransactionUpdate(BaseModel):
    date: Optional[str] = None
    type: Optional[str] = None
    source_type: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[int] = None
    payee: Optional[str] = None
    description: Optional[str] = None
    bank_name: Optional[str] = None
    receipt_path: Optional[str] = None
    ocr_data: Optional[Any] = None

class SettingUpdate(BaseModel):
    key: str
    value: str

class SyncDayRequest(BaseModel):
    date: str
    calendar_id: Optional[str] = "primary"

class SyncMonthRequest(BaseModel):
    month: str
    calendar_id: Optional[str] = "primary"


def seed_sample_data_if_empty():
    """データベースが空の場合、動作確認用のサンプルデータを投入"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM transactions")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        today = date.today().strftime("%Y-%m-%d")
        curr_month = date.today().strftime("%Y-%m")
        d1 = f"{curr_month}-02"
        d2 = f"{curr_month}-05"
        d3 = f"{curr_month}-08"
        d4 = f"{curr_month}-12"
        d5 = f"{curr_month}-15"
        d6 = f"{curr_month}-20"

        samples = [
            # 収入: Uber振込
            {
                "date": d1,
                "type": "income",
                "source_type": "uber",
                "category": "売上高",
                "amount": 48200,
                "payee": "Uber Eats (配達報酬)",
                "description": "第1週 配達パートナー売上振込",
                "bank_name": "楽天銀行"
            },
            # 収入: Rocket Now振込
            {
                "date": d2,
                "type": "income",
                "source_type": "rocket",
                "category": "売上高",
                "amount": 26500,
                "payee": "Rocket Now (デリバリー報酬)",
                "description": "即時出金 振込入金",
                "bank_name": "三井住友銀行"
            },
            # 支出: 仕入れ (レシート)
            {
                "date": d3,
                "type": "expense",
                "source_type": "purchase",
                "category": "仕入高",
                "amount": 14300,
                "payee": "業務用品問屋 丸十商事",
                "description": "梱包用資材・テイクアウト用包材仕入れ",
                "bank_name": "現金"
            },
            # 支出: 旅費交通費 (ガソリン)
            {
                "date": d4,
                "type": "expense",
                "source_type": "manual_expense",
                "category": "旅費交通費",
                "amount": 4200,
                "payee": "出光 セルフ給油",
                "description": "配達車両 レギュラー給油 28L",
                "bank_name": "クレジットカード"
            },
            # 支出: 銀行振込
            {
                "date": d5,
                "type": "expense",
                "source_type": "bank_transfer",
                "category": "通信費",
                "amount": 8900,
                "payee": "NTTドコモ / 光回線",
                "description": "業務連絡用スマホ代・光通信費 銀行口座振替",
                "bank_name": "三井住友銀行"
            },
            # 銀行管理: 入金・出金
            {
                "date": d6,
                "type": "bank",
                "source_type": "deposit",
                "category": "事業主借",
                "amount": 50000,
                "payee": "手元現金より入金",
                "description": "営業資金 口座預入",
                "bank_name": "三井住友銀行"
            }
        ]
        for s in samples:
            create_transaction(s)
        print("Initial sample transactions seeded successfully.")


@app.on_event("startup")
def startup_event():
    init_db()
    seed_sample_data_if_empty()


# -----------------------------
# 取引 API
# -----------------------------
@app.get("/api/transactions")
def list_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    month: Optional[str] = None,
    type: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None
):
    return get_transactions(
        start_date=start_date,
        end_date=end_date,
        month=month,
        trans_type=type,
        category=category,
        search=search
    )

@app.post("/api/transactions")
def add_transaction(data: TransactionCreate):
    tid = create_transaction(data.dict())
    return {"id": tid, "message": "Transaction created successfully"}

@app.get("/api/transactions/{tid}")
def get_single_transaction(tid: int):
    t = get_transaction_by_id(tid)
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return t

@app.put("/api/transactions/{tid}")
def edit_transaction(tid: int, data: TransactionUpdate):
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    updated = update_transaction(tid, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction updated successfully"}

@app.delete("/api/transactions/{tid}")
def remove_transaction(tid: int):
    deleted = delete_transaction(tid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction deleted successfully"}

# -----------------------------
# 月次集計 API
# -----------------------------
@app.get("/api/summary/monthly")
def monthly_summary(month: Optional[str] = None):
    if not month:
        month = date.today().strftime("%Y-%m")
    return get_monthly_summary(month)


# -----------------------------
# 画像アップロード & 保存 API (ローカル完全保存)
# -----------------------------
@app.post("/api/upload-receipt")
async def upload_receipt(file: UploadFile = File(...)):
    """
    レシート・領収書画像をサーバーに安全・即座に保存。
    スマホ撮影の向きズレ（EXIF）を自動補正して保存します。
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"

    unique_filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # スマホ撮影の向き（EXIF Orientation）を正立補正
    try:
        from PIL import Image, ImageOps
        with Image.open(saved_path) as img:
            transposed = ImageOps.exif_transpose(img)
            if transposed is not None:
                transposed.save(saved_path, quality=92, optimize=True)
    except Exception:
        pass

    relative_url = f"/uploads/{unique_filename}"

    return {
        "success": True,
        "storage": "local",
        "receipt_url": relative_url,
        "filename": unique_filename,
        "message": "レシート画像が正常に保存されました"
    }


# -----------------------------
# 日別収支集計 API (Googleカレンダー代替・ローカル計算)
# -----------------------------
@app.post("/api/calendar/sync-day")
def sync_day_calendar(req: SyncDayRequest):
    # Google認証なしで安全に日計収支を返す
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT type, category, amount, payee, description
        FROM transactions WHERE date = ?
    """, (req.date,))
    rows = cursor.fetchall()
    conn.close()

    income = sum(r["amount"] for r in rows if r["type"] == "income")
    expense = sum(r["amount"] for r in rows if r["type"] == "expense")
    net = income - expense
    sign = "+" if net >= 0 else ""

    summary_title = f"【収支】収入: ¥{income:,} / 支出: ¥{expense:,} (差引: {sign}¥{net:,})"
    
    return {
        "success": True,
        "mode": "local",
        "action": "calculated",
        "summary": {
            "date": req.date,
            "total_income": income,
            "total_expense": expense,
            "net": net,
            "title": summary_title
        },
        "event": {
            "summary": summary_title,
            "description": f"{req.date} の収支日計 (登録件数: {len(rows)}件)"
        }
    }

@app.post("/api/calendar/sync-month")
def sync_month_calendar(req: SyncMonthRequest):
    return {
        "success": True,
        "mode": "local",
        "month": req.month,
        "message": "月次集計完了"
    }


from urllib.parse import quote

# -----------------------------
# エクスポート API
# -----------------------------
@app.get("/api/export/excel")
def download_excel(month: Optional[str] = None):
    if not month:
        month = date.today().strftime("%Y-%m")
    excel_stream = export_to_excel(month)
    ascii_name = f"kaikei_report_{month}.xlsx"
    utf8_name = quote(f"収支報告書_{month}.xlsx")
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
        }
    )

@app.get("/api/export/pdf")
def download_pdf(month: Optional[str] = None):
    if not month:
        month = date.today().strftime("%Y-%m")
    pdf_stream = export_to_pdf(month)
    ascii_name = f"kaikei_summary_{month}.pdf"
    utf8_name = quote(f"収支計算書_{month}.pdf")
    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
        }
    )

@app.get("/api/export/csv")
def download_csv(month: Optional[str] = None, format: str = "moneyforward"):
    if not month:
        month = date.today().strftime("%Y-%m")
    
    if format == "yayoi":
        csv_text = export_yayoi_csv(month)
        ascii_name = f"yayoi_{month}.csv"
        utf8_name = quote(f"弥生会計仕訳データ_{month}.csv")
        encoded = csv_text.encode("cp932", errors="replace")
    else:
        # マネーフォワード (UTF-8 with BOM)
        csv_text = export_moneyforward_csv(month)
        ascii_name = f"mf_cloud_{month}.csv"
        utf8_name = quote(f"マネーフォワード仕訳帳_{month}.csv")
        encoded = b'\xef\xbb\xbf' + csv_text.encode("utf-8")

    return Response(
        content=encoded,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
        }
    )


# -----------------------------
# 設定 API
# -----------------------------
@app.get("/api/settings")
def get_settings():
    settings = get_all_settings()
    return {
        "default_bank_name": settings.get("default_bank_name", "三井住友銀行")
    }

@app.post("/api/settings")
def update_setting(data: SettingUpdate):
    set_setting(data.key, data.value)
    return {"message": f"Setting '{data.key}' updated successfully"}


# -----------------------------
# 静的ファイル配信 (アップロード画像・フロントエンド)
# -----------------------------
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

@app.get("/")
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "出納帳Webアプリ APIサーバー稼働中"}
