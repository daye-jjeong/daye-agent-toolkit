---
name: banksalad-import
description: 뱅크샐러드 → Obsidian vault 금융 데이터 import
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Banksalad → Obsidian Import

**Version:** 0.3.0
**Updated:** 2026-02-11

뱅크샐러드에서 메일로 받는 password-protected zip → Obsidian vault로 import.

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

## Obsidian 출력

Vault: `~/openclaw/vault`

```
~/openclaw/vault/finance/
  transactions/
    2026-02/
      2026-02-09_요기요_-14500.md
      2026-02-08_쿠팡이츠_-14200.md
  investments/
    엔비디아_키움증권.md
    TIGER_미국S&P500_미래에셋증권.md
  loans/
    주택도시기금_버팀목전세자금대출_우리은행.md
    신한은행_마이너스_통장_신한은행.md
```

## 사용법

```bash
# ~/Downloads에서 최신 뱅크샐러드 zip 자동 탐색
python {baseDir}/scripts/import_banksalad.py --latest

# 특정 파일 지정
python {baseDir}/scripts/import_banksalad.py ~/Downloads/뱅크샐러드_2025-02-09~2026-02-09.zip

# 거래내역만 import
python {baseDir}/scripts/import_banksalad.py --latest --type transactions

# dry-run (파일 생성 없이 미리보기)
python {baseDir}/scripts/import_banksalad.py --latest --dry-run

# 다른 vault 경로
python {baseDir}/scripts/import_banksalad.py --latest --vault ~/other-vault
```

## Dedup 전략

- **거래내역**: 파일명 = `{날짜}_{내용}_{금액}.md`. 이미 존재하면 skip.
- **투자**: 파일명 = `{상품명}_{금융사}.md`. 재실행 시 덮어쓰기 (평가금액 갱신).
- **대출**: 파일명 = `{상품명}_{금융사}.md`. 동명 대출은 원금으로 구분. 재실행 시 덮어쓰기.

## Dataview 쿼리 예시

```dataview
TABLE date, amount, category_l1, merchant
FROM "finance/transactions"
WHERE amount < 0
SORT date DESC
LIMIT 20
```

```dataview
TABLE institution, invested, current_value, return_pct
FROM "finance/investments"
SORT current_value DESC
```

## Frontmatter Schema

### Transaction
```yaml
type: transaction
date: 2026-02-09
time: "11:54"
amount: -14500.0
currency: KRW
tx_type: 지출
category_l1: 식사
merchant: 요기요
payment: 토스 간편결제
needs_review: true  # category_l1이 미분류이거나 비어있을 때
source: banksalad
import_key: "2026-02-09_11:54_-14500.0_요기요"
```

### Investment
```yaml
type: investment
product_type: 주식
institution: 키움증권
invested: 10616850.0
current_value: 77380019.8845
return_pct: 628.84
currency: KRW
source: banksalad
updated: 2026-02-11
```

### Loan
```yaml
type: loan
loan_type: 은행 대출
institution: 우리은행
principal: 120000000.0
outstanding: 80000000.0
interest_rate: 3.3
start_date: 2017-01-20
end_date: 2027-01-20
source: banksalad
updated: 2026-02-11
```
