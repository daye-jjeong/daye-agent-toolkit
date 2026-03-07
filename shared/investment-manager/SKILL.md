---
name: investment-manager
description: 투자 포트폴리오 현황, 종목 점검, 리스크 분석, 시세 갱신
---

# Investment Manager

투자 포트폴리오 관리 스킬. DB: `~/life-dashboard/data.db`

기존 investment-report + investment-research를 통합 대체.

## 데이터 소스

- `finance_investments` — 뱅크샐러드 import (banksalad-import 스킬)
- `finance_price_snapshots` — 시세 스냅샷 (fetch_prices.py로 갱신)

## 스크립트

### 포트폴리오 조회

```bash
python3 {baseDir}/scripts/portfolio_query.py <mode> [options]
```

| 모드 | 설명 | 옵션 |
|------|------|------|
| `summary` | 전체 현황 (KR/US 분리) | `--top N` (기본 5) |
| `risk` | 리스크 체크 | (없음) |
| `holding` | 특정 종목 상세 | `--name <종목명>` |

### 시세 갱신

```bash
python3 {baseDir}/scripts/fetch_prices.py --products "엔비디아,애플,QQQ" --prices "130.5,195.2,480.0"
```

시세 데이터는 CC 세션의 WebSearch로 조회 후 `finance_price_snapshots`에 저장.
스크립트는 DB 저장만 담당하고, 시세 조회는 LLM이 직접 수행한다.

## 사용 흐름

### 1. 현황 ("포트폴리오 보여줘", "투자 현황")
1. `portfolio_query.py summary --top 5` 실행
2. JSON을 한국어로 요약:
   - KR/US 분리 출력
   - 총 평가금액, 누적 손익, 수익률
   - Top N 보유종목 (종목/증권사/비중/수익률)
   - Top N 손실종목

### 2. 종목 점검 ("엔비디아 팔아야해?", "애플 분석해줘")
1. `portfolio_query.py holding --name <종목명>` 실행
2. 보유 현황 (증권사별 합산) 확인
3. WebSearch로 최신 뉴스/실적/시세 조회
4. 종합 분석 리포트 제공

### 3. 리스크 체크 ("리스크 체크", "포트폴리오 점검")
1. `portfolio_query.py risk` 실행
2. 경고 항목 한국어 설명:
   - 비중 쏠림: Top1 >= 35%
   - 손실군: 2개 이상 종목 수익률 <= -30%
   - 변동성: 특정 섹터 과집중

### 4. 시세 갱신 ("시세 업데이트")
1. `portfolio_query.py summary`로 보유 종목 목록 확인
2. WebSearch로 종목별 현재가 조회
3. `fetch_prices.py --products "종목1,종목2" --prices "가격1,가격2"` 로 DB 저장

## KR/US 분류 규칙

- US: institution == '토스증권' OR product_name이 'TIGER'로 시작
- KR: 나머지

## 톤 규칙

- "지금 사라/팔아라" 같은 직접 지시 금지
- "유지/비중조절 검토/리밸런싱 기준 재점검" 식 표현 사용
