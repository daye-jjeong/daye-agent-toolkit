---
name: banksalad-import
description: 뱅크샐러드 → life-dashboard SQLite DB 금융 데이터 import
version: 1.0.0
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Banksalad → Life Dashboard Import

**Version:** 1.0.0
**Updated:** 2026-03-07

뱅크샐러드에서 메일로 받는 password-protected zip → life-dashboard SQLite DB로 import.

## 입력 포맷

뱅크샐러드가 메일로 보내는 파일:
- **파일명**: `뱅크샐러드_YYYY-MM-DD~YYYY-MM-DD.zip` (비밀번호: `0830`)
- **내용물**: 하나의 xlsx 파일 (같은 날짜 범위)

### xlsx 시트 구조

| 시트 | 내용 |
|------|------|
| **뱅샐현황** (Sheet1) | 고객정보, 현금흐름(월별), 재무현황(자산/부채), 보험, 투자현황, 대출현황 |
| **가계부 내역** (Sheet2) | 개별 거래 내역 (날짜, 시간, 타입, 대분류, 소분류, 내용, 금액, 화폐, 결제수단, 메모) |

참고: 날짜는 Excel serial number (예: 46062), 시간은 fraction (예: 0.496)으로 저장됨.

## 출력

DB: `~/life-dashboard/data.db` (life-dashboard-mcp 공유)

| 테이블 | 용도 | Dedup |
|--------|------|-------|
| `finance_transactions` | 개별 거래 내역 | `import_key` UNIQUE → INSERT OR IGNORE |
| `finance_investments` | 투자 포트폴리오 | `(product_name, institution)` UNIQUE → upsert |
| `finance_loans` | 대출 현황 | `(loan_name, institution, principal)` UNIQUE → upsert |

## 사용법

```bash
# ~/Downloads에서 최신 뱅크샐러드 zip 자동 탐색
python {baseDir}/scripts/import_banksalad.py --latest

# 특정 파일 지정
python {baseDir}/scripts/import_banksalad.py ~/Downloads/뱅크샐러드_2025-02-09~2026-02-09.zip

# 거래내역만 import
python {baseDir}/scripts/import_banksalad.py --latest --type transactions

# dry-run (DB 기록 없이 미리보기)
python {baseDir}/scripts/import_banksalad.py --latest --dry-run
```

## 의존성

- `life-dashboard-mcp/db.py` — DB 연결 + 스키마 초기화
- `life-dashboard-mcp/schema.sql` — finance 테이블 정의 포함

## SQL 쿼리 예시

```sql
-- 최근 지출 20건
SELECT date, merchant, amount, category_l1
FROM finance_transactions
WHERE amount < 0
ORDER BY date DESC, time DESC
LIMIT 20;

-- 투자 포트폴리오 요약
SELECT product_name, institution, invested, current_value, return_pct
FROM finance_investments
ORDER BY current_value DESC;

-- 대출 잔액 합계
SELECT SUM(outstanding) as total_outstanding
FROM finance_loans;
```
