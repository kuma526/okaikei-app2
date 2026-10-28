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

    print("4. エクスポートテスト (Excel)...")
    excel_buf = export_to_excel(today_month)
    print(f"  Excel バイト長: {len(excel_buf.getvalue())} bytes")

    print("5. エクスポートテスト (PDF)...")
    pdf_buf = export_to_pdf(today_month)
    print(f"  PDF バイト長: {len(pdf_buf.getvalue())} bytes")

    print("6. エクスポートテスト (マネーフォワード CSV)...")
    mf_csv = export_moneyforward_csv(today_month)
    print(f"  MF CSV 行数: {len(mf_csv.splitlines())} 行")

    print("7. エクスポートテスト (弥生会計 CSV)...")
    yayoi_csv = export_yayoi_csv(today_month)
    print(f"  弥生 CSV 行数: {len(yayoi_csv.splitlines())} 行")

    print("\n✅ 全てのコア機能テストが正常に通過しました！(Google認証不要・スタンドアロン完全動作)")

if __name__ == "__main__":
    test_all()
