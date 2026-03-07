#!/usr/bin/env python3
"""
Import banksalad export xlsx into life-dashboard SQLite DB.

Usage:
  python import_banksalad.py <zip_or_xlsx>
  python import_banksalad.py <zip_or_xlsx> --type transactions
  python import_banksalad.py <zip_or_xlsx> --dry-run
  python import_banksalad.py --latest          # ~/Downloads에서 최신 뱅크샐러드 zip 자동 탐색

ZIP password: 0830 (banksalad 고정)
"""

import argparse
import re
import sqlite3
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# life-dashboard-mcp의 db 모듈 import
_DASHBOARD_DIR = Path(__file__).resolve().parent.parent.parent / "life-dashboard-mcp"
sys.path.insert(0, str(_DASHBOARD_DIR))
from db import get_conn  # noqa: E402

ZIP_PASSWORD = b"0830"
EXCEL_EPOCH = datetime(1899, 12, 30)

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


# ── xlsx 파서 (stdlib only) ───────────────────
def parse_xlsx(xlsx_path):
    """Parse xlsx using zipfile + xml.etree. Returns {sheet_name: [[cell_values]]}."""
    with zipfile.ZipFile(xlsx_path) as z:
        # shared strings
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(".//s:si", NS):
                texts = si.findall(".//s:t", NS)
                shared.append("".join(t.text or "" for t in texts))

        # sheet name → file mapping
        wb = ET.fromstring(z.read("xl/workbook.xml"))

        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_map = {}
        for r in rels.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
            rid_map[r.get("Id")] = r.get("Target")

        sheets_el = wb.findall(".//s:sheet", NS)
        result = {}
        for i, sheet_el in enumerate(sheets_el):
            name = sheet_el.get("name")
            rid = sheet_el.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = rid_map.get(rid, f"worksheets/sheet{i+1}.xml")
            sheet_path = f"xl/{target}" if not target.startswith("xl/") else target

            if sheet_path not in z.namelist():
                continue

            root = ET.fromstring(z.read(sheet_path))
            rows_data = []
            for row_el in root.findall(".//s:sheetData/s:row", NS):
                row_cells = {}
                for c in row_el.findall("s:c", NS):
                    ref = c.get("r", "")
                    col = re.match(r"([A-Z]+)", ref).group(1) if ref else ""
                    t = c.get("t", "")
                    v = c.find("s:v", NS)
                    val = v.text if v is not None else ""
                    if t == "s" and val:
                        idx = int(val)
                        val = shared[idx] if idx < len(shared) else val
                    row_cells[col] = val
                rows_data.append((int(row_el.get("r", "0")), row_cells))
            result[name] = rows_data
    return result


# ── 변환 유틸 ─────────────────────────────────
def excel_to_date(serial):
    """Excel serial number → YYYY-MM-DD string."""
    try:
        dt = EXCEL_EPOCH + timedelta(days=int(float(serial)))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(serial)


def excel_to_time(fraction):
    """Excel time fraction (0.0-1.0) → HH:MM string."""
    try:
        total_seconds = int(float(fraction) * 86400)
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        return f"{h:02d}:{m:02d}"
    except (ValueError, TypeError):
        return ""


def safe_float(val, default=0.0):
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


# ── 거래내역 import ───────────────────────────
def import_transactions(conn, sheet_rows, dry_run=False):
    """Sheet2 (가계부 내역) → finance_transactions 테이블"""
    print("=== Transactions ===")

    if not sheet_rows:
        print("  No transaction data found.")
        return

    new, skip, total = 0, 0, 0
    for row_num, cells in sheet_rows[1:]:
        date_serial = cells.get("A", "")
        if not date_serial:
            continue

        date_str = excel_to_date(date_serial)
        time_str = excel_to_time(cells.get("B", ""))
        tx_type = cells.get("C", "")
        cat1 = cells.get("D", "")
        cat2 = cells.get("E", "")
        content = cells.get("F", "")
        amount = safe_float(cells.get("G", ""))
        currency = cells.get("H", "KRW") or "KRW"
        payment = cells.get("I", "")
        memo = cells.get("J", "")

        total += 1
        import_key = f"{date_str}_{time_str}_{amount}_{content}_{payment}"[:120]

        if dry_run:
            if new < 3:
                print(f"  [dry-run] {date_str} {content} {amount:+,.0f}")
            new += 1
            continue

        try:
            conn.execute("""
                INSERT INTO finance_transactions
                    (date, time, amount, currency, tx_type, category_l1,
                     category_l2, merchant, payment, memo, import_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str, time_str or None, amount, currency,
                tx_type or None, cat1 or None,
                cat2 if cat2 and cat2 != "미분류" else None,
                content or None, payment or None, memo or None,
                import_key,
            ))
            new += 1
        except sqlite3.IntegrityError:
            skip += 1

    if not dry_run:
        conn.commit()
    print(f"  Result: {new} new, {skip} skipped (dup), {total} total")


# ── 투자현황 import ───────────────────────────
def import_investments(conn, sheet_rows, dry_run=False):
    """Sheet1 section 5 (투자현황) → finance_investments 테이블"""
    print("=== Investments ===")

    start_idx = None
    for i, (row_num, cells) in enumerate(sheet_rows):
        for val in cells.values():
            if "5.투자현황" in str(val):
                start_idx = i
                break
        if start_idx is not None:
            break

    if start_idx is None:
        print("  Investment section not found.")
        return

    header_idx = start_idx + 2
    if header_idx >= len(sheet_rows):
        print("  No investment header found.")
        return

    new, updated = 0, 0

    for i in range(header_idx + 1, len(sheet_rows)):
        row_num, cells = sheet_rows[i]
        product_type = cells.get("B", "")
        if "총계" in product_type:
            break
        if not product_type:
            continue

        institution = cells.get("C", "")
        name = cells.get("D", "")
        if not name or "보유상품" in name:
            continue

        invested = safe_float(cells.get("F", ""))
        current_val = safe_float(cells.get("G", ""))
        return_pct = safe_float(cells.get("H", ""))

        if invested == 0 and current_val == 0:
            continue

        if dry_run:
            if new + updated < 3:
                print(f"  [dry-run] {name} ({current_val:,.0f})")
            new += 1
            continue

        exists = conn.execute(
            "SELECT 1 FROM finance_investments WHERE product_name=? AND institution=?",
            (name, institution),
        ).fetchone()
        conn.execute("""
            INSERT INTO finance_investments
                (product_name, product_type, institution, invested,
                 current_value, return_pct)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_name, institution) DO UPDATE SET
                product_type=excluded.product_type,
                invested=excluded.invested,
                current_value=excluded.current_value,
                return_pct=excluded.return_pct,
                updated_at=datetime('now','localtime')
        """, (name, product_type, institution, invested, current_val, round(return_pct, 2)))
        if exists:
            updated += 1
        else:
            new += 1

    if not dry_run:
        conn.commit()
    print(f"  Result: {new} new, {updated} updated")


# ── 대출현황 import ───────────────────────────
def import_loans(conn, sheet_rows, dry_run=False):
    """Sheet1 section 6 (대출현황) → finance_loans 테이블"""
    print("=== Loans ===")

    start_idx = None
    for i, (row_num, cells) in enumerate(sheet_rows):
        for val in cells.values():
            if "6.대출현황" in str(val):
                start_idx = i
                break
        if start_idx is not None:
            break

    if start_idx is None:
        print("  Loan section not found.")
        return

    header_idx = start_idx + 2
    new, updated = 0, 0

    for i in range(header_idx + 1, len(sheet_rows)):
        row_num, cells = sheet_rows[i]
        loan_type = cells.get("B", "")
        if "총계" in loan_type:
            break
        if not loan_type:
            continue

        institution = cells.get("C", "")
        name = cells.get("D", "")
        if not name or "보유 대출" in name:
            continue

        principal = safe_float(cells.get("F", ""))
        outstanding = safe_float(cells.get("G", ""))
        rate = safe_float(cells.get("H", ""))
        start_serial = cells.get("I", "")
        end_serial = cells.get("J", "")
        start_date = excel_to_date(start_serial) if start_serial else None
        end_date = excel_to_date(end_serial) if end_serial else None

        if dry_run:
            print(f"  [dry-run] {name} (잔액 {outstanding:,.0f})")
            new += 1
            continue

        exists = conn.execute(
            "SELECT 1 FROM finance_loans WHERE loan_name=? AND institution=? AND principal=?",
            (name, institution, principal),
        ).fetchone()
        conn.execute("""
            INSERT INTO finance_loans
                (loan_name, loan_type, institution, principal,
                 outstanding, interest_rate, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(loan_name, institution, principal) DO UPDATE SET
                loan_type=excluded.loan_type,
                outstanding=excluded.outstanding,
                interest_rate=excluded.interest_rate,
                start_date=excluded.start_date,
                end_date=excluded.end_date,
                updated_at=datetime('now','localtime')
        """, (name, loan_type, institution, principal, outstanding, rate, start_date, end_date))
        if exists:
            updated += 1
        else:
            new += 1

    if not dry_run:
        conn.commit()
    print(f"  Result: {new} new, {updated} updated")


# ── zip 처리 ──────────────────────────────────
def extract_xlsx_from_zip(zip_path):
    """Password-protected zip에서 xlsx 추출."""
    import shutil
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmpdir, pwd=ZIP_PASSWORD)
        xlsx_files = list(Path(tmpdir).glob("*.xlsx"))
        if not xlsx_files:
            print(f"Error: No xlsx found in {zip_path}")
            sys.exit(1)
        dest = Path(tempfile.mktemp(suffix=".xlsx"))
        shutil.copy2(xlsx_files[0], dest)
        return dest


def find_latest_banksalad_zip():
    """~/Downloads에서 최신 뱅크샐러드 zip 찾기."""
    downloads = Path("~/Downloads").expanduser()
    candidates = []
    for f in downloads.iterdir():
        if f.suffix == ".zip" and ("뱅크" in f.name or "banksalad" in f.name.lower()):
            candidates.append(f)
        elif f.suffix == ".zip" and re.search(r"\d{4}-\d{2}-\d{2}.*~.*\d{4}-\d{2}-\d{2}", f.name):
            candidates.append(f)
    if not candidates:
        for f in downloads.iterdir():
            if f.suffix == ".zip" and "~" in f.name and re.search(r"\d{4}-\d{2}-\d{2}", f.name):
                candidates.append(f)
    if not candidates:
        print("Error: ~/Downloads에서 뱅크샐러드 zip 파일을 찾을 수 없습니다.")
        sys.exit(1)
    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    print(f"Found: {candidates[0].name}")
    return candidates[0]


# ── main ──────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Import banksalad xlsx to life-dashboard DB")
    parser.add_argument("input", nargs="?", type=Path, help="Path to banksalad zip or xlsx")
    parser.add_argument("--latest", action="store_true", help="~/Downloads에서 최신 zip 자동 탐색")
    parser.add_argument("--type", default="all", choices=["all", "transactions", "investments", "loans"])
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't write to DB")
    args = parser.parse_args()

    # resolve input
    if args.latest:
        input_path = find_latest_banksalad_zip()
    elif args.input:
        input_path = args.input
    else:
        parser.print_help()
        sys.exit(1)

    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    # extract xlsx if zip
    xlsx_path = input_path
    tmp_xlsx = None
    if input_path.suffix == ".zip":
        print(f"Extracting xlsx from {input_path.name}...")
        xlsx_path = extract_xlsx_from_zip(input_path)
        tmp_xlsx = xlsx_path

    # parse
    print(f"Parsing {xlsx_path.name}...")
    sheets = parse_xlsx(xlsx_path)

    sheet1_name = next((n for n in sheets if "현황" in n), None)
    sheet2_name = next((n for n in sheets if "가계부" in n or "내역" in n), None)

    if args.dry_run:
        print("[DRY RUN MODE]")

    conn = None if args.dry_run else get_conn()

    if args.type in ("all", "investments") and sheet1_name:
        import_investments(conn, sheets[sheet1_name], args.dry_run)
    if args.type in ("all", "loans") and sheet1_name:
        import_loans(conn, sheets[sheet1_name], args.dry_run)
    if args.type in ("all", "transactions") and sheet2_name:
        import_transactions(conn, sheets[sheet2_name], args.dry_run)

    if conn:
        conn.close()

    # cleanup
    if tmp_xlsx and tmp_xlsx.exists():
        tmp_xlsx.unlink()

    print("\nDone!")


if __name__ == "__main__":
    main()
