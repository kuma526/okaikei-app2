"""
システム結合テストスクリプト
"""
import sys
import os

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_db, get_transactions, get_monthly_summary, create_transaction
from backend.app import seed_sample_data_if_empty
from backend.ocr_service import analyze_receipt
from backend.calendar_service import calculate_daily_summary, sync_daily_to_calendar
from backend.export_service import export_to_excel, export_to_pdf, export_moneyforward_csv, export_yayoi_csv

def test_all():
    print("1. データベース初期化テスト...")
    init_db()
    seed_sample_data_if_empty()

    print("2. 取引取得テスト...")
    today_month = "2026-10"
    trans = get_transactions(month=today_month)
    print(f"  取得件数: {len(trans)} 件")

    print("3. 月次集計テスト...")
    summary = get_monthly_summary(today_month)
    print(f"  総収入: ¥{summary['total_income']:,}")
    print(f"  総支出: ¥{summary['total_expense']:,}")
    print(f"  差引利益: ¥{summary['net_income']:,}")

    print("4. カレンダー同期集計テスト...")
    daily = calculate_daily_summary("2026-10-02")
    print(f"  タイトル: {daily['title']}")
    res = sync_daily_to_calendar("2026-10-02")
    print(f"  同期結果モード: {res.get('mode')}")

    print("5. エクスポートテスト (Excel)...")
    excel_buf = export_to_excel(today_month)
    print(f"  Excel バイト長: {len(excel_buf.getvalue())} bytes")

    print("6. エクスポートテスト (PDF)...")
    pdf_buf = export_to_pdf(today_month)
    print(f"  PDF バイト長: {len(pdf_buf.getvalue())} bytes")

    print("7. エクスポートテスト (マネーフォワード CSV)...")
    mf_csv = export_moneyforward_csv(today_month)
    print(f"  MF CSV 行数: {len(mf_csv.splitlines())} 行")

    print("8. エクスポートテスト (弥生会計 CSV)...")
    yayoi_csv = export_yayoi_csv(today_month)
    print(f"  弥生 CSV 行数: {len(yayoi_csv.splitlines())} 行")

    print("9. OCR スマートフォールバック・推論テスト...")
    dummy_ocr = analyze_receipt("dummy.jpg", "shiire_receipt_202610.jpg", api_key="")
    print(f"  AI推測科目: {dummy_ocr['suggested_category']}")
    print(f"  推測金額: ¥{dummy_ocr['total_amount']:,}")
    print(f"  品目数: {len(dummy_ocr['items'])} 件")

    print("\n✅ 全てのモジュールテストが正常に通過しました！")

if __name__ == "__main__":
    test_all()
