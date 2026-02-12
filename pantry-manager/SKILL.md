---
name: pantry-manager
description: 식재료 관리 자동화 — 재고, 유통기한, 쇼핑리스트, 레시피 추천
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Pantry Manager Skill

**Version:** 0.2.0 | **Updated:** 2026-02-12 | **Status:** Experimental

식재료 관리 자동화 스킬. Obsidian vault 기반 재고 관리, 유통기한 알림, 장보기 목록, 레시피 추천.

## 트리거

사용자가 다음을 요청할 때 활성화:
- "양파 5개 추가해줘, 유통기한 2월 15일"
- "유통기한 임박한 식재료 알려줘"
- "냉장고에 뭐 있어?"
- "오늘 저녁 뭐 만들 수 있어?"
- "장보기 목록 만들어줘"
- "영수증 사진으로 식재료 추가해줘" (이미지 첨부)

## 설치 & 설정

Python3만 필요. 별도 API 키 불필요.

## Core Workflow

1. **추가**: 식재료 정보를 vault에 등록 (이름, 카테고리, 수량, 유통기한, 위치)
2. **조회**: 전체/카테고리별/위치별 식재료 목록 조회
3. **유통기한 체크**: 임박(3일 이내) + 만료 식재료 알림
4. **장보기 목록**: 부족/만료 항목 기반 자동 생성
5. **레시피 추천**: 현재 재고 기반 저속노화 메뉴 추천
6. **이미지 파싱**: 영수증 사진에서 식재료 자동 추출 (OCR)

## Scripts

| Script | Purpose |
|--------|---------|
| `pantry_io.py` | Vault 기반 식재료 I/O 모듈 |
| `add_item.py` | 식재료 추가 |
| `list_items.py` | 목록 조회 (--category, --location) |
| `check_expiry.py` | 유통기한 체크 |
| `shopping_list.py` | 장보기 목록 생성 |
| `recipe_suggest.py` | 레시피 추천 |
| `parse_receipt.py` | 영수증 이미지 파싱 |
| `weekly_check.py` | 주간 냉장고 정리 체크 + 알림 |

**상세 (명령어 예시, 크론 설정)**: `{baseDir}/references/usage-examples.md` 참고

## 자동화

- 매일 09:00: 유통기한 체크 -> Telegram 알림
- 매주 일 20:00: 냉장고 정리 체크 -> Telegram 알림

## Data Storage

- **Vault:** `~/clawd/memory/pantry/items/` (각 식재료 = 개별 .md, YAML frontmatter)
- **환경변수:** `PANTRY_VAULT` (기본값: `~/clawd/memory`)
- **로컬 캐시:** `~/.cache/pantry-manager/` (임시 리포트, 이미지 파싱 결과)

## Frontmatter Schema

```yaml
type: pantry-item
name: 당근
category: 채소
quantity: 5
unit: 개
location: 냉장
purchase_date: 2026-02-10
expiry_date: 2026-02-20
status: 재고 있음
updated: 2026-02-12
```

## Dataview 쿼리 예시

```dataview
TABLE name, category, quantity, unit, location, expiry_date, status
FROM "pantry/items"
WHERE type = "pantry-item"
SORT expiry_date ASC
```
