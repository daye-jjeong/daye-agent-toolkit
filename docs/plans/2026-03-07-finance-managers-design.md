## Design

investment-manager + spending-manager 스킬 신규 생성.
기존 investment-report, investment-research는 삭제하고 통합 대체.

### 데이터 소스

- `~/life-dashboard/data.db` (life-dashboard-mcp/db.py 공유)
- 외부 시세: WebSearch → finance_price_snapshots 저장

### 스키마 추가 (schema.sql)

- `finance_price_snapshots` — 일별 시세 스냅샷
- `finance_merchant_categories` — 미분류 merchant → 카테고리 매핑

### Skill 1: investment-manager

기존 investment-report + investment-research 통합.

| 모드 | 트리거 | 동작 |
|------|--------|------|
| 현황 | "포트폴리오 보여줘" | DB → 종목별 평가/손익/비중 출력 |
| 점검 | "엔비디아 팔아야해?" | DB + WebSearch → 분석 리포트 |
| 리스크 | "리스크 체크" | 비중 쏠림, 손실군, 변동성 경고 |
| 시세 갱신 | "시세 업데이트" | WebSearch → price_snapshots 저장 |

스크립트:
- `scripts/portfolio_query.py` — 포트폴리오 현황/리스크 JSON
- `scripts/fetch_prices.py` — 시세 조회 + DB 저장

### Skill 2: spending-manager

신규.

| 모드 | 트리거 | 동작 |
|------|--------|------|
| 요약 | "이번달 소비" | 기간별 카테고리 요약 + 고정비/변동비 분리 |
| 추세 | "소비 추세" | 월별 비교, 카테고리별 증감 |
| 분석 | "어디서 많이 쓰지" | Top merchant, 반복 지출 |
| 재분류 | "미분류 정리" | merchant_categories 기반 매핑 |
| 예산 | "예산 설정" | coach_state에 예산 저장 → 초과 경고 |

스크립트:
- `scripts/spending_query.py` — 기간/카테고리 집계 JSON

---

## Plan

### Phase 1: 스키마 + spending-manager
- [x] 1. schema.sql에 finance_price_snapshots, finance_merchant_categories 추가
- [x] 2. spending-manager/SKILL.md 작성
- [x] 3. spending-manager/scripts/spending_query.py 구현
- [x] 4. spending-manager/.claude-skill 생성
- [x] 5. 동작 테스트 (실제 DB 쿼리)

### Phase 2: investment-manager
- [x] 6. investment-manager/SKILL.md 작성
- [x] 7. investment-manager/scripts/portfolio_query.py 구현
- [x] 8. investment-manager/scripts/fetch_prices.py 구현
- [x] 9. investment-manager/.claude-skill 생성
- [x] 10. 동작 테스트

### Phase 3: 정리
- [x] 11. 기존 investment-report, investment-research 삭제
- [x] 12. CLAUDE.md 업데이트
- [x] 13. 최종 검증 + 커밋
