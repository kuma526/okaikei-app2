import os
import io
import csv
from datetime import datetime
from typing import List, Dict, Any
from backend.database import get_transactions, get_monthly_summary

# openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# reportlab
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 日本語フォントの登録（Windows / Mac / Linuxクラウド環境すべてに対応）
FONT_NAME = "Helvetica"
def setup_pdf_fonts():
    global FONT_NAME
    font_paths = [
        "C:\\Windows\\Fonts\\msgothic.ttc",
        "C:\\Windows\\Fonts\\msmincho.ttc",
        "C:\\Windows\\Fonts\\meiryo.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc"
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont("JapaneseFont", p))
                FONT_NAME = "JapaneseFont"
                return
            except Exception as e:
                print(f"Font register error with {p}: {e}")

    # クラウド・Linux環境用フォールバック（ReportLab標準の日本語CIDフォント）
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        FONT_NAME = "HeiseiKakuGo-W5"
    except Exception as e:
        print(f"CID Font fallback error: {e}")

setup_pdf_fonts()


def export_to_excel(month: str) -> io.BytesIO:
    """指定月の収支明細およびサマリーをExcel形式で出力"""
    summary = get_monthly_summary(month)
    transactions = get_transactions(month=month)

    wb = Workbook()
    
    # -----------------------------
    # Sheet 1: 月次収支サマリー
    # -----------------------------
    ws_summary = wb.active
    ws_summary.title = "月次収支サマリー"
    ws_summary.views.sheetView[0].showGridLines = True

    # スタイル定義
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    accent_fill = PatternFill(start_color="0284C7", end_color="0284C7", fill_type="solid")
    sub_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    card_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    font_title = Font(name="Meiryo", size=16, bold=True, color="1E293B")
    font_header = Font(name="Meiryo", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Meiryo", size=11, bold=True, color="1E293B")
    font_main = Font(name="Meiryo", size=10, color="334155")
    font_number = Font(name="Meiryo", size=10, color="0F172A")

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # タイトル
    ws_summary.merge_cells("A1:F1")
    ws_summary["A1"] = f"個人事業主 月次収支報告書（{month}度）"
    ws_summary["A1"].font = font_title
    ws_summary["A1"].alignment = Alignment(vertical="center")
    ws_summary.row_dimensions[1].height = 35

    ws_summary["A2"] = f"作成日: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}"
    ws_summary["A2"].font = Font(name="Meiryo", size=9, color="64748B")

    # 主要業績サマリーカード
    cards = [
        ("総収入 (売上)", summary["total_income"], "10B981"),
        ("総支出 (経費・仕入)", summary["total_expense"], "EF4444"),
        ("差引手取収支 (粗利益)", summary["net_income"], "0284C7")
    ]
    
    col_idx = 1
    for label, val, hex_color in cards:
        cell_label = ws_summary.cell(row=4, column=col_idx, value=label)
        cell_label.font = Font(name="Meiryo", size=10, bold=True, color="475569")
        cell_label.fill = sub_fill
        cell_label.border = thin_border
        cell_label.alignment = Alignment(horizontal="center", vertical="center")

        cell_val = ws_summary.cell(row=5, column=col_idx, value=val)
        cell_val.font = Font(name="Meiryo", size=14, bold=True, color=hex_color)
        cell_val.number_format = '"¥"#,##0'
        cell_val.fill = card_fill
        cell_val.border = thin_border
        cell_val.alignment = Alignment(horizontal="right", vertical="center")

        ws_summary.column_dimensions[get_column_letter(col_idx)].width = 22
        col_idx += 1

    # 収入内訳テーブル
    ws_summary.cell(row=7, column=1, value="【収入の内訳】").font = font_bold
    ws_summary.cell(row=8, column=1, value="区分").font = font_header
    ws_summary.cell(row=8, column=1).fill = header_fill
    ws_summary.cell(row=8, column=2, value="金額").font = font_header
    ws_summary.cell(row=8, column=2).fill = header_fill
    ws_summary.cell(row=8, column=3, value="件数").font = font_header
    ws_summary.cell(row=8, column=3).fill = header_fill

    source_names = {
        "uber": "Uber 振込売上",
        "rocket": "Rocket Now 振込売上",
        "manual_income": "その他手動売上"
    }
    
    r_idx = 9
    for st_key, st_label in source_names.items():
        st_data = summary["income_by_source"].get(st_key, {"total": 0, "count": 0})
        ws_summary.cell(row=r_idx, column=1, value=st_label).font = font_main
        ws_summary.cell(row=r_idx, column=1).border = thin_border

        c_tot = ws_summary.cell(row=r_idx, column=2, value=st_data["total"])
        c_tot.font = font_number
        c_tot.number_format = '"¥"#,##0'
        c_tot.border = thin_border

        c_cnt = ws_summary.cell(row=r_idx, column=3, value=f"{st_data['count']} 件")
        c_cnt.font = font_main
        c_cnt.border = thin_border
        c_cnt.alignment = Alignment(horizontal="center")
        r_idx += 1

    # 支出（勘定科目別）内訳テーブル
    r_idx += 1
    ws_summary.cell(row=r_idx, column=1, value="【支出（勘定科目別）の内訳】").font = font_bold
    r_idx += 1
    ws_summary.cell(row=r_idx, column=1, value="勘定科目").font = font_header
    ws_summary.cell(row=r_idx, column=1).fill = accent_fill
    ws_summary.cell(row=r_idx, column=2, value="金額").font = font_header
    ws_summary.cell(row=r_idx, column=2).fill = accent_fill
    ws_summary.cell(row=r_idx, column=3, value="構成比 / 件数").font = font_header
    ws_summary.cell(row=r_idx, column=3).fill = accent_fill
    r_idx += 1

    tot_exp = summary["total_expense"] or 1
    for cat_item in summary["expense_by_category"]:
        ratio = (cat_item["total"] / tot_exp) * 100
        ws_summary.cell(row=r_idx, column=1, value=cat_item["category"]).font = font_main
        ws_summary.cell(row=r_idx, column=1).border = thin_border

        c_tot = ws_summary.cell(row=r_idx, column=2, value=cat_item["total"])
        c_tot.font = font_number
        c_tot.number_format = '"¥"#,##0'
        c_tot.border = thin_border

        c_cnt = ws_summary.cell(row=r_idx, column=3, value=f"{ratio:.1f}% ({cat_item['count']}件)")
        c_cnt.font = font_main
        c_cnt.border = thin_border
        c_cnt.alignment = Alignment(horizontal="center")
        r_idx += 1

    # -----------------------------
    # Sheet 2: 全取引明細一覧
    # -----------------------------
    ws_details = wb.create_sheet(title="全取引明細一覧")
    ws_details.views.sheetView[0].showGridLines = True

    columns = [
        ("No", 6),
        ("取引日", 12),
        ("区分", 10),
        ("取引種別", 16),
        ("勘定科目", 14),
        ("金額 (税込)", 14),
        ("取引先 / 店名", 22),
        ("摘要 / 品目・メモ", 30),
        ("決済口座", 14),
        ("レシート画像", 12)
    ]

    for col_i, (col_name, col_width) in enumerate(columns, start=1):
        c = ws_details.cell(row=1, column=col_i, value=col_name)
        c.font = font_header
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws_details.column_dimensions[get_column_letter(col_i)].width = col_width

    ws_details.row_dimensions[1].height = 28

    type_labels = {"income": "収入", "expense": "支出", "bank": "銀行"}
    source_labels = {
        "uber": "Uber振込", "rocket": "Rocket Now振込", "manual_income": "手動売上",
        "purchase": "仕入れ", "bank_transfer": "銀行振込", "manual_expense": "その他経費",
        "deposit": "銀行入金", "withdrawal": "銀行出金"
    }

    for row_i, t in enumerate(transactions, start=2):
        ws_details.row_dimensions[row_i].height = 22
        fill = sub_fill if row_i % 2 == 0 else PatternFill(fill_type=None)

        ws_details.cell(row=row_i, column=1, value=row_i-1).alignment = Alignment(horizontal="center")
        ws_details.cell(row=row_i, column=2, value=t["date"]).alignment = Alignment(horizontal="center")
        ws_details.cell(row=row_i, column=3, value=type_labels.get(t["type"], t["type"])).alignment = Alignment(horizontal="center")
        ws_details.cell(row=row_i, column=4, value=source_labels.get(t["source_type"], t["source_type"]))
        ws_details.cell(row=row_i, column=5, value=t["category"])

        amt_cell = ws_details.cell(row=row_i, column=6, value=t["amount"])
        amt_cell.number_format = '"¥"#,##0'
        amt_cell.alignment = Alignment(horizontal="right")

        ws_details.cell(row=row_i, column=7, value=t["payee"])
        ws_details.cell(row=row_i, column=8, value=t["description"])
        ws_details.cell(row=row_i, column=9, value=t["bank_name"])
        ws_details.cell(row=row_i, column=10, value="あり" if t["receipt_path"] else "なし").alignment = Alignment(horizontal="center")

        for c_i in range(1, 11):
            cell = ws_details.cell(row=row_i, column=c_i)
            cell.font = font_main
            cell.border = thin_border
            if row_i % 2 == 0:
                cell.fill = fill

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def export_to_pdf(month: str) -> io.BytesIO:
    """指定月の税務確認用・見やすいPDF集計表を出力"""
    summary = get_monthly_summary(month)
    transactions = get_transactions(month=month)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        fontName=FONT_NAME,
        fontSize=18,
        leading=22,
        alignment=1, # Center
        textColor=colors.HexColor("#0F172A")
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        alignment=2, # Right
        textColor=colors.HexColor("#64748B")
    )
    heading_style = ParagraphStyle(
        'SectionHeading',
        fontName=FONT_NAME,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=6
    )
    cell_style = ParagraphStyle(
        'TableCell',
        fontName=FONT_NAME,
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#334155")
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        fontName=FONT_NAME,
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#0F172A")
    )
    cell_right = ParagraphStyle(
        'TableCellRight',
        fontName=FONT_NAME,
        fontSize=9,
        leading=11,
        alignment=2,
        textColor=colors.HexColor("#0F172A")
    )

    elements = []

    # 表紙・タイトル
    elements.append(Paragraph(f"【税務確認用】月次収支計算書・損益集計表", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"対象期間: {month}度 ｜ 出力日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 12))

    # 1. 損益計算サマリー表 (損益計算書スタイル)
    elements.append(Paragraph("■ 月次損益サマリー（青色申告決算書・収支内訳書準拠）", heading_style))

    uber_tot = summary["income_by_source"].get("uber", {}).get("total", 0)
    rocket_tot = summary["income_by_source"].get("rocket", {}).get("total", 0)
    manual_inc_tot = summary["income_by_source"].get("manual_income", {}).get("total", 0)
    total_income = summary["total_income"]

    # 仕入れと経費の分離
    purchase_tot = 0
    expenses_only = []
    for c in summary["expense_by_category"]:
        if c["category"] == "仕入高":
            purchase_tot += c["total"]
        else:
            expenses_only.append(c)

    gross_profit = total_income - purchase_tot
    total_operating_expense = sum(c["total"] for c in expenses_only)
    net_income = summary["net_income"]

    pl_data = [
        [Paragraph("科目 / 区分", cell_bold), Paragraph("金額 (税込)", cell_bold), Paragraph("摘要・内訳", cell_bold)],
        [Paragraph("<b>Ⅰ. 売上高 (収入金額)</b>", cell_style), Paragraph(f"<b>¥{total_income:,}</b>", cell_right), Paragraph(f"Uber: ¥{uber_tot:,} / Rocket Now: ¥{rocket_tot:,} / 他: ¥{manual_inc_tot:,}", cell_style)],
        [Paragraph("<b>Ⅱ. 売上原価 (仕入高)</b>", cell_style), Paragraph(f"¥{purchase_tot:,}", cell_right), Paragraph("商品仕入れ・直接原価", cell_style)],
        [Paragraph("<b>Ⅲ. 差引売上総利益 (粗利益)</b>", cell_bold), Paragraph(f"<b>¥{gross_profit:,}</b>", cell_right), Paragraph("Ⅰ 売上高 － Ⅱ 仕入高", cell_style)],
        [Paragraph("<b>Ⅳ. 経費合計</b>", cell_style), Paragraph(f"¥{total_operating_expense:,}", cell_right), Paragraph("消耗品費・交通費・通信費などの合算", cell_style)],
        [Paragraph("<b>Ⅴ. 所得金額 (差引手取利益)</b>", cell_bold), Paragraph(f"<b>¥{net_income:,}</b>", cell_right), Paragraph("Ⅲ 差引売上総利益 － Ⅳ 経費合計", cell_style)],
    ]

    pl_table = Table(pl_data, colWidths=[160, 110, 250])
    pl_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor("#F8FAFC")),
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor("#E0F2FE")),
    ]))
    elements.append(pl_table)
    elements.append(Spacer(1, 14))

    # 2. 経費科目別内訳表
    elements.append(Paragraph("■ 経費科目別内訳", heading_style))
    exp_data = [
        [Paragraph("勘定科目", cell_bold), Paragraph("金額", cell_bold), Paragraph("件数", cell_bold), Paragraph("構成比", cell_bold)]
    ]
    tot_exp = summary["total_expense"] or 1
    for c in summary["expense_by_category"]:
        ratio = (c["total"] / tot_exp) * 100
        exp_data.append([
            Paragraph(c["category"], cell_style),
            Paragraph(f"¥{c['total']:,}", cell_right),
            Paragraph(f"{c['count']} 件", cell_style),
            Paragraph(f"{ratio:.1f}%", cell_style),
        ])
    if len(exp_data) == 1:
        exp_data.append([Paragraph("経費データなし", cell_style), Paragraph("¥0", cell_right), Paragraph("0件", cell_style), Paragraph("0%", cell_style)])

    exp_table = Table(exp_data, colWidths=[150, 110, 80, 80])
    exp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(exp_table)
    elements.append(Spacer(1, 14))

    # 3. 取引明細一覧
    elements.append(Paragraph(f"■ 取引明細一覧（全 {len(transactions)} 件）", heading_style))
    trans_data = [
        [Paragraph("日付", cell_bold), Paragraph("区分/科目", cell_bold), Paragraph("取引先 / 摘要", cell_bold), Paragraph("金額", cell_bold)]
    ]
    for t in transactions:
        desc_text = t["payee"]
        if t["description"]:
            desc_text += f" ({t['description']})"
        if not desc_text:
            desc_text = "-"
        
        prefix = "+" if t["type"] == "income" else ("-" if t["type"] == "expense" else "")
        amt_str = f"{prefix}¥{t['amount']:,}"
        
        trans_data.append([
            Paragraph(t["date"], cell_style),
            Paragraph(f"{t['category']}", cell_style),
            Paragraph(desc_text[:35], cell_style),
            Paragraph(amt_str, cell_right),
        ])
    if len(trans_data) == 1:
        trans_data.append([Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("取引履歴なし", cell_style), Paragraph("¥0", cell_right)])

    trans_table = Table(trans_data, colWidths=[80, 110, 230, 100])
    trans_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(trans_table)

    # ビルド
    doc.build(elements)
    buffer.seek(0)
    return buffer


def export_moneyforward_csv(month: str) -> str:
    """
    マネーフォワード クラウド確定申告形式のCSV文字列を生成
    公式仕訳インポート用カラム定義に準拠
    """
    transactions = get_transactions(month=month)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")

    # MF クラウド仕訳帳ヘッダー
    headers = [
        "取引No", "取引日", "借方勘定科目", "借方補助科目", "借方税区分", "借方金額(円)",
        "貸方勘定科目", "貸方補助科目", "貸方税区分", "貸方金額(円)",
        "摘要", "仕訳メモ", "タグ", "MF仕訳タイプ"
    ]
    writer.writerow(headers)

    for i, t in enumerate(transactions, start=1):
        amt = t["amount"]
        dt = t["date"].replace("-", "/")
        payee = t["payee"] or ""
        desc = t["description"] or ""
        memo = f"{payee} {desc}".strip()
        account = t["bank_name"] or "普通預金"

        if t["type"] == "income":
            # 借方: 預金/現金, 貸方: 売上高
            dr_account = account
            dr_tax = "対象外"
            cr_account = "売上高"
            cr_tax = "課税売上 10%"
            summary_text = f"売上入金 ({t['source_type']}) {memo}".strip()
        elif t["type"] == "expense":
            # 借方: 費用科目 (仕入高, 消耗品費等), 貸方: 預金/現金
            dr_account = t["category"]
            dr_tax = "課税仕入 10%"
            cr_account = account
            cr_tax = "対象外"
            summary_text = f"{t['category']} {memo}".strip()
        else: # 銀行
            if t["source_type"] == "deposit":
                dr_account = account
                dr_tax = "対象外"
                cr_account = "事業主借"
                cr_tax = "対象外"
                summary_text = f"預金入金 {memo}".strip()
            else:
                dr_account = "事業主貸"
                dr_tax = "対象外"
                cr_account = account
                cr_tax = "対象外"
                summary_text = f"預金出金 {memo}".strip()

        row = [
            i, dt, dr_account, "", dr_tax, amt,
            cr_account, "", cr_tax, amt,
            summary_text, f"ID:{t['id']}", "", ""
        ]
        writer.writerow(row)

    return output.getvalue()


def export_yayoi_csv(month: str) -> str:
    """
    弥生会計 / やよいの青色申告形式のCSV文字列を生成
    弥生の仕訳データインポートフォーマットに準拠
    """
    transactions = get_transactions(month=month)
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\r\n")

    # 弥生会計形式（ヘッダーなし、または標準カラム）
    for i, t in enumerate(transactions, start=1):
        amt = t["amount"]
        dt = t["date"].replace("-", "/")
        payee = t["payee"] or ""
        desc = t["description"] or ""
        memo = f"{payee} {desc}".strip()
        account = t["bank_name"] or "普通預金"

        if t["type"] == "income":
            dr_account = account
            dr_tax = "対象外"
            cr_account = "売上高"
            cr_tax = "課税売上 10%"
            summary_text = f"売上 ({t['source_type']}) {memo}".strip()
        elif t["type"] == "expense":
            dr_account = t["category"]
            dr_tax = "課税仕入 10%"
            cr_account = account
            cr_tax = "対象外"
            summary_text = f"{t['category']} {memo}".strip()
        else:
            if t["source_type"] == "deposit":
                dr_account = account
                dr_tax = "対象外"
                cr_account = "事業主借"
                cr_tax = "対象外"
                summary_text = f"預金入金 {memo}".strip()
            else:
                dr_account = "事業主貸"
                dr_tax = "対象外"
                cr_account = account
                cr_tax = "対象外"
                summary_text = f"預金出金 {memo}".strip()

        row = [
            "2000",          # 識別フラグ
            "",              # 伝票No
            "",              # 決算
            dt,              # 取引日付
            dr_account,      # 借方勘定科目
            "",              # 借方補助科目
            "",              # 借方部門
            dr_tax,          # 借方税区分
            amt,             # 借方金額
            0,               # 借方税額
            cr_account,      # 貸方勘定科目
            "",              # 貸方補助科目
            "",              # 貸方部門
            cr_tax,          # 貸方税区分
            amt,             # 貸方金額
            0,               # 貸方税額
            summary_text,    # 摘要
            "",              # 番号
            "",              # 期日
            "3",             # タイプ (振替伝票)
            "",              # 生成元
            "",              # 仕訳メモ
            "",              # 付箋1
            "",              # 付箋2
            "no"             # 調整
        ]
        writer.writerow(row)

    return output.getvalue()

