import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from backend.database import get_db_connection, set_setting, get_setting

# Google Calendar 連携用
try:
    from google.oauth2.credentials import Credentials
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service(credentials_path: Optional[str] = None):
    """Google Calendar API サービスを初期化（環境変数 GOOGLE_CREDENTIALS_JSON または ファイルに対応）"""
    if not GOOGLE_LIBS_AVAILABLE:
        return None

    # 1. クラウドデプロイ用: 環境変数 GOOGLE_CREDENTIALS_JSON を優先チェック
    env_creds = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()
    if env_creds:
        try:
            cred_data = json.loads(env_creds)
            if cred_data.get("type") == "service_account":
                creds = service_account.Credentials.from_service_account_info(cred_data, scopes=SCOPES)
                return build('calendar', 'v3', credentials=creds)
        except Exception as e:
            print(f"Calendar env credentials parse error: {e}")

    # 2. ローカルファイル (credentials.json / service_account.json) をチェック
    creds_path = credentials_path or get_setting("google_credentials_path", "credentials.json")
    if not os.path.isabs(creds_path):
        creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), creds_path)

    if not os.path.exists(creds_path):
        alt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "service_account.json")
        if os.path.exists(alt_path):
            creds_path = alt_path
        else:
            return None

    try:
        # サービスアカウントかOAuthかを判定
        with open(creds_path, "r", encoding="utf-8") as f:
            cred_data = json.load(f)

        if cred_data.get("type") == "service_account":
            creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
            return build('calendar', 'v3', credentials=creds)
        elif "installed" in cred_data or "web" in cred_data:
            # OAuth 認証情報
            token_path = os.path.join(os.path.dirname(creds_path), "token.json")
            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"Calendar service initialization error: {e}")
        return None

    return None

def calculate_daily_summary(target_date: str) -> Dict[str, Any]:
    """指定された日付（YYYY-MM-DD）の収支集計と内訳を算出"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT type, source_type, category, amount, payee, description
        FROM transactions
        WHERE date = ?
    """, (target_date,))
    rows = cursor.fetchall()
    conn.close()

    total_income = 0
    total_expense = 0
    income_details = []
    expense_details = []

    for r in rows:
        amt = r["amount"]
        t = r["type"]
        st = r["source_type"]
        cat = r["category"]
        payee = r["payee"] or ""
        desc = r["description"] or ""

        label = payee if payee else cat
        if desc:
            label += f" ({desc})"

        if t == "income":
            total_income += amt
            income_details.append(f"  ・{label}: ¥{amt:,}")
        elif t == "expense":
            total_expense += amt
            expense_details.append(f"  ・{label} [{cat}]: ¥{amt:,}")

    net = total_income - total_expense
    sign = "+" if net >= 0 else ""

    summary_title = f"【収支】収入: ¥{total_income:,} / 支出: ¥{total_expense:,} (差引: {sign}¥{net:,})"
    
    desc_lines = [
        f"=== {target_date} 収支日計 ===",
        f"■ 収入合計: ¥{total_income:,}",
    ]
    if income_details:
        desc_lines.extend(income_details)
    else:
        desc_lines.append("  (収入なし)")

    desc_lines.append(f"\n■ 支出合計: ¥{total_expense:,}")
    if expense_details:
        desc_lines.extend(expense_details)
    else:
        desc_lines.append("  (支出なし)")

    desc_lines.append(f"\n■ 差引手取収支: {sign}¥{net:,}")
    desc_lines.append("\n※個人事業主出納帳Webアプリより自動同期")

    return {
        "date": target_date,
        "total_income": total_income,
        "total_expense": total_expense,
        "net": net,
        "title": summary_title,
        "description": "\n".join(desc_lines),
        "count": len(rows)
    }

def sync_daily_to_calendar(target_date: str, calendar_id: str = "primary") -> Dict[str, Any]:
    """
    指定日の収支合計をGoogleカレンダーの非公開終日イベントとして同期。
    重複を検知した場合は更新する。
    """
    summary = calculate_daily_summary(target_date)
    cal_id = calendar_id or get_setting("google_calendar_id", "primary")
    service = get_calendar_service()

    event_body = {
        'summary': summary['title'],
        'description': summary['description'],
        'start': {
            'date': target_date,
        },
        'end': {
            'date': target_date,
        },
        'visibility': 'private', # 非公開予定
        'transparency': 'transparent', # 予定あり（取り込み中）ではなく空き時間扱い
    }

    if not service:
        # サービス未接続時はシミュレーションモードで結果を返す
        return {
            "success": True,
            "mode": "preview",
            "message": "Googleカレンダー連携のプレビューです。Google認証情報（credentials.json）を配置すると自動でGoogleカレンダーへ反映されます。",
            "event": event_body,
            "summary": summary
        }

    try:
        # 同一日付の既存同期イベントを検索
        time_min = f"{target_date}T00:00:00Z"
        time_max = f"{target_date}T23:59:59Z"
        events_result = service.events().list(
            calendarId=cal_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            q="【収支】"
        ).execute()

        items = events_result.get('items', [])
        if items:
            existing_event_id = items[0]['id']
            updated_event = service.events().update(
                calendarId=cal_id,
                eventId=existing_event_id,
                body=event_body
            ).execute()
            event_id = updated_event['id']
            action = "updated"
        else:
            created_event = service.events().insert(
                calendarId=cal_id,
                body=event_body
            ).execute()
            event_id = created_event['id']
            action = "created"

        # ログ記録
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO calendar_sync_logs (sync_date, status, event_id, summary, synced_at)
            VALUES (?, ?, ?, ?, ?)
        """, (target_date, action, event_id, summary['title'], datetime.now().isoformat()))
        conn.commit()
        conn.close()

        return {
            "success": True,
            "mode": "live",
            "action": action,
            "event_id": event_id,
            "event": event_body,
            "summary": summary
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "summary": summary
        }

def sync_month_to_calendar(month: str, calendar_id: str = "primary") -> Dict[str, Any]:
    """月内の全取引日についてGoogleカレンダー同期を一括実行"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT date FROM transactions
        WHERE strftime('%Y-%m', date) = ?
        ORDER BY date ASC
    """, (month,))
    dates = [r["date"] for r in cursor.fetchall()]
    conn.close()

    results = []
    for d in dates:
        res = sync_daily_to_calendar(d, calendar_id)
        results.append(res)

    return {
        "month": month,
        "processed_dates_count": len(dates),
        "results": results
    }

