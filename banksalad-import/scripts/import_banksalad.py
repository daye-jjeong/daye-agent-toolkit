#!/usr/bin/env python3
"""
Import banksalad export xlsx into Obsidian vault as Dataview-queryable markdown.

Usage:
  python import_banksalad.py <zip_or_xlsx>
  python import_banksalad.py <zip_or_xlsx> --type transactions
  python import_banksalad.py <zip_or_xlsx> --dry-run
  python import_banksalad.py --latest          # ~/Downloads에서 최신 뱅크샐러드 zip 자동 탐색

ZIP password: 0830 (banksalad 고정)
"""

import argparse
import os
import re
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# ── 설정 ──────────────────────────────────────
VAULT_DIR = Path("~/mingming-vault").expanduser()
FINANCE_DIR = VAULT_DIR / "finance"
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
        sheet_names = [s.get("name") for s in wb.findall(".//s:sheet", NS)]

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


def sanitize_filename(name, max_len=60):
    """파일시스템 안전한 이름으로 변환."""
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', "", name)
    name = name.replace(" ", "_").strip("._")
    return name[:max_len] if name else "unknown"


def safe_float(val, default=0.0):
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


# ── 거래내역 import ───────────────────────────
def import_transactions(sheet_rows, dry_run=False):
    """Sheet2 (가계부 내역) → finance/transactions/YYYY-MM/*.md"""
    print("=== Transactions ===")
    tx_dir = FINANCE_DIR / "transactions"

    # first row is header
    if not sheet_rows:
        print("  No transaction data found.")
        return

    # column mapping from first row
    header_row = sheet_rows[0][1]
    col_map = {}
    for col, val in header_row.items():
        col_map[val] = col
    # Expected: 날짜=A, 시간=B, 타입=C, 대분류=D, 소분류=E, 내용=F, 금액=G, 화폐=H, 결제수단=I, 메모=J

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
        month = date_str[:7]  # YYYY-MM
        month_dir = tx_dir / month

        # filename with dedup key
        import_key = f"{date_str}_{time_str}_{amount}_{content}"[:100]
        safe_content = sanitize_filename(content) if content else sanitize_filename(cat1)
        fname = f"{date_str}_{safe_content}_{int(amount)}.md"
        fpath = month_dir / fname

        if fpath.exists():
            skip += 1
            continue

        # frontmatter
        fm_lines = [
            "---",
            "type: transaction",
            f"date: {date_str}",
        ]
        if time_str:
            fm_lines.append(f'time: "{time_str}"')
        fm_lines.append(f"amount: {amount}")
        fm_lines.append(f"currency: {currency}")
        if tx_type:
            fm_lines.append(f"tx_type: {tx_type}")
        if cat1:
            fm_lines.append(f"category_l1: {cat1}")
        if cat2 and cat2 != "미분류":
            fm_lines.append(f"category_l2: {cat2}")
        if content:
            fm_lines.append(f"merchant: {content}")
        if payment:
            fm_lines.append(f"payment: {payment}")
        fm_lines.extend([
            "source: banksalad",
            f'import_key: "{import_key}"',
        ])
        if memo:
            fm_lines.append(f"memo: {memo}")
        fm_lines.append("---")

        # title
        display_name = content or cat1 or "거래"
        title = f"# {display_name} ({amount:+,.0f} {currency})"

        md_content = "\n".join(fm_lines) + f"\n\n{title}\n"

        if dry_run:
            if new < 3:
                print(f"  [dry-run] {fpath.relative_to(VAULT_DIR)}")
            new += 1
            continue

        month_dir.mkdir(parents=True, exist_ok=True)
        fpath.write_text(md_content, encoding="utf-8")
        new += 1

        if new % 200 == 0:
            print(f"  Progress: {new + skip}/{total}...")

    print(f"  Result: {new} new, {skip} skipped (dup), {total} total")


# ── 투자현황 import ───────────────────────────
def import_investments(sheet_rows, dry_run=False):
    """Sheet1 section 5 (투자현황) → finance/investments/*.md"""
    print("=== Investments ===")
    inv_dir = FINANCE_DIR / "investments"

    # find section 5 start
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

    # header row is start_idx + 2 (skip description row)
    header_idx = start_idx + 2
    if header_idx >= len(sheet_rows):
        print("  No investment header found.")
        return

    # parse rows until 총계 row
    export_date = datetime.now().strftime("%Y-%m-%d")
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

        safe_name = sanitize_filename(name)
        safe_inst = sanitize_filename(institution)
        fname = f"{safe_name}_{safe_inst}.md"
        fpath = inv_dir / fname

        fm_lines = [
            "---",
            "type: investment",
            f"product_type: {product_type}",
            f"institution: {institution}",
            f"invested: {invested}",
            f"current_value: {current_val}",
            f"return_pct: {round(return_pct, 2)}",
            "currency: KRW",
            "source: banksalad",
            f"updated: {export_date}",
            "---",
        ]

        pnl = current_val - invested
        title = f"# {name}"
        body = f"\n{institution} | 투자원금 {invested:,.0f} → 평가 {current_val:,.0f} ({return_pct:+.1f}%)"

        md_content = "\n".join(fm_lines) + f"\n\n{title}\n{body}\n"

        if dry_run:
            if new + updated < 3:
                print(f"  [dry-run] {fname} ({current_val:,.0f})")
            if fpath.exists():
                updated += 1
            else:
                new += 1
            continue

        inv_dir.mkdir(parents=True, exist_ok=True)
        is_update = fpath.exists()
        fpath.write_text(md_content, encoding="utf-8")
        if is_update:
            updated += 1
        else:
            new += 1

    print(f"  Result: {new} new, {updated} updated")


# ── 대출현황 import ───────────────────────────
def import_loans(sheet_rows, dry_run=False):
    """Sheet1 section 6 (대출현황) → finance/loans/*.md"""
    print("=== Loans ===")
    loan_dir = FINANCE_DIR / "loans"

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
    seen_loan_names = set()

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
        start_date = excel_to_date(start_serial) if start_serial else ""
        end_date = excel_to_date(end_serial) if end_serial else ""

        safe_name = sanitize_filename(name)
        safe_inst = sanitize_filename(institution)
        fname = f"{safe_name}_{safe_inst}.md"
        fpath = loan_dir / fname
        # 같은 이름의 대출이 여러 건일 수 있음 (예: 마이너스통장 2개)
        if fpath.exists() or fname in seen_loan_names:
            fname = f"{safe_name}_{safe_inst}_{int(principal)}.md"
            fpath = loan_dir / fname
        seen_loan_names.add(fname)

        fm_lines = [
            "---",
            "type: loan",
            f"loan_type: {loan_type}",
            f"institution: {institution}",
            f"principal: {principal}",
            f"outstanding: {outstanding}",
            f"interest_rate: {rate}",
        ]
        if start_date:
            fm_lines.append(f"start_date: {start_date}")
        if end_date:
            fm_lines.append(f"end_date: {end_date}")
        fm_lines.extend([
            "source: banksalad",
            f"updated: {datetime.now().strftime('%Y-%m-%d')}",
            "---",
        ])

        title = f"# {name}"
        body = f"\n{institution} | 원금 {principal:,.0f} | 잔액 {outstanding:,.0f} | 금리 {rate}%"

        md_content = "\n".join(fm_lines) + f"\n\n{title}\n{body}\n"

        if dry_run:
            print(f"  [dry-run] {fname}")
            if fpath.exists():
                updated += 1
            else:
                new += 1
            continue

        loan_dir.mkdir(parents=True, exist_ok=True)
        is_update = fpath.exists()
        fpath.write_text(md_content, encoding="utf-8")
        if is_update:
            updated += 1
        else:
            new += 1

    print(f"  Result: {new} new, {updated} updated")


# ── zip 처리 ──────────────────────────────────
def extract_xlsx_from_zip(zip_path):
    """Password-protected zip에서 xlsx 추출."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmpdir, pwd=ZIP_PASSWORD)
        xlsx_files = list(Path(tmpdir).glob("*.xlsx"))
        if not xlsx_files:
            print(f"Error: No xlsx found in {zip_path}")
            sys.exit(1)
        # copy to a stable temp location (tmpdir will be cleaned up)
        import shutil
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
        # try URL-encoded or broken filenames with date range pattern
        for f in downloads.iterdir():
            if f.suffix == ".zip" and "~" in f.name and re.search(r"\d{4}-\d{2}-\d{2}", f.name):
                candidates.append(f)
    if not candidates:
        print("Error: ~/Downloads에서 뱅크샐러드 zip 파일을 찾을 수 없습니다.")
        sys.exit(1)
    # most recently modified
    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    print(f"Found: {candidates[0].name}")
    return candidates[0]


# ── main ──────────────────────────────────────
def main():
    global VAULT_DIR, FINANCE_DIR

    parser = argparse.ArgumentParser(description="Import banksalad xlsx to Obsidian vault")
    parser.add_argument("input", nargs="?", type=Path, help="Path to banksalad zip or xlsx")
    parser.add_argument("--latest", action="store_true", help="~/Downloads에서 최신 zip 자동 탐색")
    parser.add_argument("--type", default="all", choices=["all", "transactions", "investments", "loans"])
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't write files")
    parser.add_argument("--vault", type=Path, help="Obsidian vault path (default: ~/mingming-vault)")
    args = parser.parse_args()

    if args.vault:
        VAULT_DIR = args.vault.expanduser()
        FINANCE_DIR = VAULT_DIR / "finance"

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

    if args.type in ("all", "investments") and sheet1_name:
        import_investments(sheets[sheet1_name], args.dry_run)
    if args.type in ("all", "loans") and sheet1_name:
        import_loans(sheets[sheet1_name], args.dry_run)
    if args.type in ("all", "transactions") and sheet2_name:
        import_transactions(sheets[sheet2_name], args.dry_run)

    # cleanup
    if tmp_xlsx and tmp_xlsx.exists():
        tmp_xlsx.unlink()

    print("\nDone!")


if __name__ == "__main__":
    main()
