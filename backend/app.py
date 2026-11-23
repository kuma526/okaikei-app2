import os
import io
import uuid
import shutil
import base64
import json
import urllib.request
import urllib.error
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from urllib.parse import quote
import requests
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Response, Request
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

# Google Apps Script Webhook URL設定（環境変数 GAS_WEBHOOK_URL から読み込み）
GAS_WEBHOOK_URL = os.environ.get("GAS_WEBHOOK_URL", "").strip()

# アプリ初期化
app = FastAPI(title="勘太郎 ver. 1.0", version="1.0.0")

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
    source_type: str # 'store', 'uber', 'rocket', 'manual_income', 'purchase', 'bank_transfer', 'manual_expense', 'deposit', 'withdrawal'
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
        curr_month = date.today().strftime("%Y-%m")
        d1 = f"{curr_month}-02"
        d2 = f"{curr_month}-05"
        d3 = f"{curr_month}-08"
        d4 = f"{curr_month}-12"
        d5 = f"{curr_month}-15"
        d6 = f"{curr_month}-20"

        samples = [
            # 収入: 店舗売上 (現金)
            {
                "date": d1,
                "type": "income",
                "source_type": "store",
                "category": "売上高",
                "amount": 35000,
                "payee": "店舗売上 (現金)",
                "description": "ランチタイム店頭現金売上",
                "bank_name": "現金"
            },
            # 収入: 店舗売上 (楽天ターミナル・カード)
            {
                "date": d1,
                "type": "income",
                "source_type": "store",
                "category": "売上高",
                "amount": 18000,
                "payee": "店舗売上 (楽天ターミナル)",
                "description": "カード決済 (総額: ¥18,000 / 手数料(3.24%): ¥583 / 受取額: ¥17,417)",
                "bank_name": "楽天ターミナル",
                "ocr_data": {
                    "fee_calculation": {
                        "gross_amount": 18000,
                        "fee_rate": 3.24,
                        "fee_amount": 583,
                        "net_amount": 17417,
                        "payment_type": "カード"
                    }
                }
            },
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

@app.get("/api/transactions/{id}")
def get_single_transaction(id: int):
    t = get_transaction_by_id(id)
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return t

@app.put("/api/transactions/{id}")
def edit_transaction(id: int, data: TransactionUpdate):
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    updated = update_transaction(id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"message": "Transaction updated successfully"}

@app.delete("/api/transactions/{id}")
def remove_transaction(id: int):
    deleted = delete_transaction(id)
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
# 画像アップロード & 保存 API (ローカル + Googleドライブ GAS自動転送)
# -----------------------------
@app.post("/api/upload-receipt")
async def upload_receipt(request: Request, file: Optional[UploadFile] = File(None)):
    """
    レシート・領収書画像を受け取り、Google Apps Script (GAS) Webhook へ
    Base64エンコードしたJSON形式 {"filename": "...", "file": "..."} でPOST転送して
    Googleドライブに保存します。返却されたGoogleドライブのURLを返します。
    """
    content_type = request.headers.get("content-type", "")
    today_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_id = uuid.uuid4().hex[:6]
    
    filename = ""
    file_bytes = b""
    b64_data = ""
    ext = ".jpg"

    # 1. JSON (Base64直接送信) の場合
    if "application/json" in content_type:
        try:
            body = await request.json()
            filename = body.get("filename", "")
            raw_file_str = body.get("file") or body.get("base64") or ""
            if "," in raw_file_str:
                # data:image/png;base64,... 形式のプレフィックスを除去
                b64_data = raw_file_str.split(",", 1)[1]
            else:
                b64_data = raw_file_str
            
            if b64_data:
                file_bytes = base64.b64decode(b64_data)
        except Exception as e:
            print(f"JSON Parse Error: {e}")

    # 2. FormData (ファイルアップロード) の場合
    elif file is not None:
        filename = file.filename
        file_bytes = await file.read()
        b64_data = base64.b64encode(file_bytes).decode("utf-8")
    else:
        # Request form のフォールバック
        form = await request.form()
        uploaded = form.get("file")
        if uploaded and hasattr(uploaded, "filename"):
            filename = uploaded.filename
            file_bytes = await uploaded.read()
            b64_data = base64.b64encode(file_bytes).decode("utf-8")
        elif "file" in form and isinstance(form["file"], str):
            raw_file_str = form["file"]
            b64_data = raw_file_str.split(",", 1)[1] if "," in raw_file_str else raw_file_str
            file_bytes = base64.b64decode(b64_data)

    if filename:
        ext = os.path.splitext(filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"

    unique_filename = f"receipt_{today_str}_{random_id}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_filename)

    # ローカルへバックアップ保存
    if file_bytes:
        with open(saved_path, "wb") as buffer:
            buffer.write(file_bytes)

        # スマホ撮影の向き（EXIF Orientation）を正立補正
        try:
            from PIL import Image, ImageOps
            with Image.open(saved_path) as img:
                transposed = ImageOps.exif_transpose(img)
                if transposed is not None:
                    transposed.save(saved_path, quality=92, optimize=True)
            with open(saved_path, "rb") as f:
                file_bytes = f.read()
            # 補正後のBase64を再作成
            b64_data = base64.b64encode(file_bytes).decode("utf-8")
        except Exception:
            pass

    mime_type = "image/jpeg"
    if ext == ".png":
        mime_type = "image/png"
    elif ext == ".webp":
        mime_type = "image/webp"

    # ローカルURL（フォールバック用）
    relative_url = f"/uploads/{unique_filename}"
    storage_type = "local"
    drive_file_url = None

    # Google Apps Script (GAS) へのアップロード処理
    gas_url = os.environ.get("GAS_WEBHOOK_URL", "").strip() or GAS_WEBHOOK_URL or get_setting("gas_webhook_url", "").strip()
    if gas_url and b64_data:
        try:
            gas_payload = {
                "filename": unique_filename,
                "file": b64_data
            }
            # requests で GAS Webhook へ POST 送信
            response = requests.post(
                gas_url,
                json=gas_payload,
                headers={"Content-Type": "application/json"},
                allow_redirects=True,
                timeout=35
            )
            if response.status_code == 200:
                try:
                    res_data = response.json()
                    if isinstance(res_data, dict):
                        drive_file_url = (
                            res_data.get("url") or
                            res_data.get("fileUrl") or
                            res_data.get("file_url") or
                            res_data.get("receipt_url") or
                            res_data.get("drive_url") or
                            res_data.get("webViewLink")
                        )
                        if not drive_file_url and isinstance(res_data.get("data"), dict):
                            drive_file_url = res_data["data"].get("url") or res_data["data"].get("fileUrl")
                    elif isinstance(res_data, str) and (res_data.startswith("http://") or res_data.startswith("https://")):
                        drive_file_url = res_data
                except Exception:
                    # プレーンテキストでURLが返ってきた場合のフォールバック
                    text_resp = response.text.strip().strip('"\'')
                    if text_resp.startswith("http://") or text_resp.startswith("https://"):
                        drive_file_url = text_resp

            if drive_file_url:
                relative_url = drive_file_url
                storage_type = "gdrive"
        except Exception as e:
            # GASへの転送に失敗した場合でも、ローカル保存されたURLで続行
            print(f"GAS Upload Error: {e}")

    return {
        "success": True,
        "storage": storage_type,
        "receipt_url": relative_url,
        "filename": unique_filename,
        "gdrive_url": drive_file_url,
        "message": "レシート画像がGoogleドライブに正常保存されました" if storage_type == "gdrive" else "レシート画像が保存されました"
    }


# -----------------------------
# 日別収支集計 API (Google不要・ローカル計算)
# -----------------------------
@app.post("/api/calendar/sync-day")
def sync_day_calendar(req: SyncDayRequest):
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


# -----------------------------
# エクスポート API (Excel / PDF / MF CSV / 弥生 CSV)
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
        "default_bank_name": settings.get("default_bank_name", "三井住友銀行"),
        "card_fee_rate": settings.get("card_fee_rate", "3.24"),
        "gas_webhook_url": settings.get("gas_webhook_url", os.environ.get("GAS_WEBHOOK_URL", ""))
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
