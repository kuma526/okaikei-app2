import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "kaikei.db")

def get_db_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        type TEXT NOT NULL, -- 'income', 'expense', 'bank'
        source_type TEXT NOT NULL, -- 'uber', 'rocket', 'manual_income', 'purchase', 'bank_transfer', 'manual_expense', 'deposit', 'withdrawal'
        category TEXT NOT NULL, -- 勘定科目
        amount INTEGER NOT NULL,
        payee TEXT DEFAULT '', -- 取引先 / 店舗名
        description TEXT DEFAULT '', -- 品目・メモ
        bank_name TEXT DEFAULT '通常口座', -- 銀行名・口座
        receipt_path TEXT DEFAULT '', -- レシート画像パス
        ocr_data TEXT DEFAULT '', -- AI解析詳細JSON (品目リスト等)
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS calendar_sync_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sync_date TEXT NOT NULL,
        status TEXT NOT NULL,
        event_id TEXT DEFAULT '',
        summary TEXT DEFAULT '',
        synced_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()

def get_all_settings() -> Dict[str, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

def create_transaction(data: Dict[str, Any]) -> int:
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (
            date, type, source_type, category, amount, payee, description,
            bank_name, receipt_path, ocr_data, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("date", datetime.now().strftime("%Y-%m-%d")),
        data.get("type", "expense"),
        data.get("source_type", "manual_expense"),
        data.get("category", "雑費"),
        int(data.get("amount", 0)),
        data.get("payee", ""),
        data.get("description", ""),
        data.get("bank_name", "現金"),
        data.get("receipt_path", ""),
        json.dumps(data.get("ocr_data", {}), ensure_ascii=False) if isinstance(data.get("ocr_data"), (dict, list)) else (data.get("ocr_data") or ""),
        now,
        now
    ))
    trans_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trans_id

def get_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    month: Optional[str] = None,
    trans_type: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []

    if month:
        query += " AND strftime('%Y-%m', date) = ?"
        params.append(month)
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    if trans_type:
        query += " AND type = ?"
        params.append(trans_type)
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (payee LIKE ? OR description LIKE ? OR category LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])

    query += " ORDER BY date DESC, id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        if d.get("ocr_data"):
            try:
                d["ocr_data"] = json.loads(d["ocr_data"])
            except Exception:
                pass
        result.append(d)
    return result

def get_transaction_by_id(trans_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE id = ?", (trans_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("ocr_data"):
        try:
            d["ocr_data"] = json.loads(d["ocr_data"])
        except Exception:
            pass
    return d

def update_transaction(trans_id: int, data: Dict[str, Any]) -> bool:
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    fields = []
    values = []
    for k in ["date", "type", "source_type", "category", "amount", "payee", "description", "bank_name", "receipt_path"]:
        if k in data:
            fields.append(f"{k} = ?")
            values.append(int(data[k]) if k == "amount" else data[k])
    
    if "ocr_data" in data:
        fields.append("ocr_data = ?")
        val = data["ocr_data"]
        values.append(json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else (val or ""))

    fields.append("updated_at = ?")
    values.append(now)
    values.append(trans_id)

    query = f"UPDATE transactions SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, values)
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def delete_transaction(trans_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (trans_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_monthly_summary(month: str) -> Dict[str, Any]:
    """
    指定月（YYYY-MM）の収支集計、カテゴリ別内訳、Uber/Rocket Now別、日別集計
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 総収入（Uber, Rocket, 手動など）
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM transactions 
        WHERE strftime('%Y-%m', date) = ? AND type = 'income'
    """, (month,))
    total_income = cursor.fetchone()[0]

    # 総支出（仕入れ、銀行振込、その他経費など）
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM transactions 
        WHERE strftime('%Y-%m', date) = ? AND type = 'expense'
    """, (month,))
    total_expense = cursor.fetchone()[0]

    # 銀行入金・出金
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM transactions 
        WHERE strftime('%Y-%m', date) = ? AND type = 'bank' AND source_type = 'deposit'
    """, (month,))
    bank_deposits = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM transactions 
        WHERE strftime('%Y-%m', date) = ? AND type = 'bank' AND source_type = 'withdrawal'
    """, (month,))
    bank_withdrawals = cursor.fetchone()[0]

    # 収入のソース別（Uber, Rocket Now, その他）
    cursor.execute("""
        SELECT source_type, COALESCE(SUM(amount), 0) as total, COUNT(*) as count
        FROM transactions
        WHERE strftime('%Y-%m', date) = ? AND type = 'income'
        GROUP BY source_type
    """, (month,))
    income_by_source = {r["source_type"]: {"total": r["total"], "count": r["count"]} for r in cursor.fetchall()}

    # 支出のカテゴリ別（仕入高、消耗品費など）
    cursor.execute("""
        SELECT category, COALESCE(SUM(amount), 0) as total, COUNT(*) as count
        FROM transactions
        WHERE strftime('%Y-%m', date) = ? AND type = 'expense'
        GROUP BY category
        ORDER BY total DESC
    """, (month,))
    expense_by_category = [{"category": r["category"], "total": r["total"], "count": r["count"]} for r in cursor.fetchall()]

    # 日別の集計（カレンダー同期やグラフ用）
    cursor.execute("""
        SELECT 
            date,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expense,
            SUM(CASE WHEN type = 'bank' AND source_type = 'deposit' THEN amount ELSE 0 END) as bank_in,
            SUM(CASE WHEN type = 'bank' AND source_type = 'withdrawal' THEN amount ELSE 0 END) as bank_out
        FROM transactions
        WHERE strftime('%Y-%m', date) = ?
        GROUP BY date
        ORDER BY date ASC
    """, (month,))
    daily_stats = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "month": month,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_income": total_income - total_expense,
        "bank_deposits": bank_deposits,
        "bank_withdrawals": bank_withdrawals,
        "income_by_source": income_by_source,
        "expense_by_category": expense_by_category,
        "daily_stats": daily_stats
    }


def is_sample_transaction(t: Dict[str, Any]) -> bool:
    """本番環境に混入させないダミー/サンプルデータ判定"""
    sample_payees = {
        "出光 セルフ給油",
        "業務用品問屋 丸十商事",
        "業務卸問屋 丸十商事",
        "Uber Eats (配達報酬)",
        "Rocket Now (デリバリー報酬)"
    }
    sample_descriptions = {
        "ランチタイム店頭現金売上",
        "カード決済 (総額: ¥18,000 / 手数料(3.24%): ¥583 / 受取額: ¥17,417)",
        "第1週 配達パートナー売上振込",
        "即時出金 振込入金",
        "梱包用資材・テイクアウト用包材仕入れ",
        "配達車両 レギュラー給油 28L",
        "業務連絡用スマホ代・光通信費 銀行口座振替",
        "営業資金 口座預入"
    }
    payee = str(t.get("payee") or "").strip()
    desc = str(t.get("description") or "").strip()
    if payee in sample_payees:
        return True
    if desc in sample_descriptions:
        return True
    return False


def purge_sample_data() -> int:
    """DB内に残存するダミー/サンプルデータを一掃する"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM transactions 
        WHERE payee IN ('出光 セルフ給油', '業務用品問屋 丸十商事', '業務卸問屋 丸十商事', 'Uber Eats (配達報酬)', 'Rocket Now (デリバリー報酬)')
           OR description IN (
               'ランチタイム店頭現金売上',
               'カード決済 (総額: ¥18,000 / 手数料(3.24%): ¥583 / 受取額: ¥17,417)',
               '第1週 配達パートナー売上振込',
               '即時出金 振込入金',
               '梱包用資材・テイクアウト用包材仕入れ',
               '配達車両 レギュラー給油 28L',
               '業務連絡用スマホ代・光通信費 銀行口座振替',
               '営業資金 口座預入'
           )
    """)
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def restore_transactions_to_db(items: List[Dict[str, Any]], replace: bool = False) -> int:
    """外部バックアップ（JSONファイルまたはGoogleドライブ）の取引リストをDBに復元・同期する。
    replace=True の場合、既存データを消去した上で完全復元する。
    replace=False の場合、既存データとマージ・同期する。
    """
    if not isinstance(items, list):
        return 0
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    imported_count = 0

    if replace:
        cursor.execute("DELETE FROM transactions")
        conn.commit()

    for item in items:
        if is_sample_transaction(item):
            continue

        raw_id = item.get("id")
        t_id = None
        if raw_id is not None:
            try:
                t_id = int(raw_id)
            except (ValueError, TypeError):
                t_id = None

        ocr_val = item.get("ocr_data", {})
        if isinstance(ocr_val, (dict, list)):
            ocr_str = json.dumps(ocr_val, ensure_ascii=False)
        else:
            ocr_str = str(ocr_val or "")

        date_val = str(item.get("date") or datetime.now().strftime("%Y-%m-%d"))
        type_val = str(item.get("type") or "expense")
        source_type_val = str(item.get("source_type") or "manual_expense")
        category_val = str(item.get("category") or "雑費")
        try:
            amount_val = int(item.get("amount") or 0)
        except (ValueError, TypeError):
            amount_val = 0
        payee_val = str(item.get("payee") or "")
        desc_val = str(item.get("description") or "")
        bank_name_val = str(item.get("bank_name") or "現金")
        receipt_path_val = str(item.get("receipt_path") or "")

        exists = False
        if not replace and t_id is not None:
            cursor.execute("SELECT id FROM transactions WHERE id = ?", (t_id,))
            row = cursor.fetchone()
            if row:
                exists = True
                cursor.execute("""
                    UPDATE transactions SET
                        date = ?, type = ?, source_type = ?, category = ?,
                        amount = ?, payee = ?, description = ?, bank_name = ?,
                        receipt_path = ?, ocr_data = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    date_val, type_val, source_type_val, category_val,
                    amount_val, payee_val, desc_val, bank_name_val,
                    receipt_path_val, ocr_str, now, t_id
                ))
                imported_count += 1

        if not exists:
            if not replace:
                cursor.execute("""
                    SELECT id FROM transactions 
                    WHERE date = ? AND type = ? AND amount = ? AND payee = ? AND description = ?
                """, (date_val, type_val, amount_val, payee_val, desc_val))
                row = cursor.fetchone()
            else:
                row = None

            if not row:
                if t_id is not None and replace:
                    cursor.execute("""
                        INSERT INTO transactions (
                            id, date, type, source_type, category, amount, payee,
                            description, bank_name, receipt_path, ocr_data, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        t_id, date_val, type_val, source_type_val, category_val, amount_val, payee_val,
                        desc_val, bank_name_val, receipt_path_val, ocr_str, now, now
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO transactions (
                            date, type, source_type, category, amount, payee,
                            description, bank_name, receipt_path, ocr_data, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        date_val, type_val, source_type_val, category_val, amount_val, payee_val,
                        desc_val, bank_name_val, receipt_path_val, ocr_str, now, now
                    ))
                imported_count += 1

    conn.commit()
    conn.close()
    return imported_count


def sync_transactions_to_db(items: List[Dict[str, Any]]) -> int:
    """外部バックアップ（JSONファイルまたはGoogleドライブ）の取引リストをDBに同期・マージする。"""
    return restore_transactions_to_db(items, replace=False)



