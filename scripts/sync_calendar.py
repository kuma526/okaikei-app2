"""
Googleカレンダー日次・月次自動同期スクリプト
Windowsタスクスケジューラ等に登録して毎晩自動実行できます。
"""
import sys
import os
from datetime import date, timedelta

# ルートパス追加
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.calendar_service import sync_daily_to_calendar, sync_month_to_calendar

def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else date.today().strftime("%Y-%m-%d")
    print(f"=== Googleカレンダー収支同期バッチ開始: {target_date} ===")
    
    res = sync_daily_to_calendar(target_date)
    if res.get("success"):
        mode = res.get("mode")
        action = res.get("action", "processed")
        print(f"同期成功 [{mode}]: {res.get('summary', {}).get('title')}")
        if mode == "preview":
            print("※Google認証ファイル未配置のためプレビューモードで実行されました。")
    else:
        print(f"エラー: {res.get('error')}")

if __name__ == "__main__":
    main()

