---
name: pantry-manager
description: 식재료 관리 자동화 — 재고, 쇼핑리스트, 레시피 추천
version: 1.0.0
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Pantry Manager Skill

**Version:** 0.3.0 | **Updated:** 2026-03-08

식재료 관리 스킬. life-dashboard SQLite 기반 CRUD, 장보기 목록, 레시피 추천.
유통기한 알림은 life-coach 일일 코칭에서 처리.

## 트리거

사용자가 다음을 요청할 때 활성화:
- "양파 5개 추가해줘, 유통기한 2월 15일"
- "냉장고에 뭐 있어?"
- "오늘 저녁 뭐 만들 수 있어?"
- "장보기 목록 만들어줘"
- "영수증 사진으로 식재료 추가해줘" (이미지 첨부)

## 설치 & 설정

Python3만 필요. 데이터는 life-dashboard-mcp SQLite (`~/life-dashboard/data.db`)에 저장.

## Core Workflow

1. **추가**: 식재료 정보를 DB에 등록 (이름, 카테고리, 수량, 유통기한, 위치)
2. **조회**: 전체/카테고리별/위치별 식재료 목록 조회
3. **장보기 목록**: '부족' 상태 항목 기반 자동 생성
4. **레시피 추천**: 현재 재고 기반 저속노화 메뉴 추천
5. **이미지 파싱**: 영수증 사진에서 식재료 자동 추출 (OCR)

## Scripts

| Script | Purpose |
|--------|---------|
| `add_item.py` | 식재료 추가 (upsert) |
| `list_items.py` | 목록 조회 (--category, --location, --json) |
| `shopping_list.py` | 장보기 목록 생성 |
| `recipe_suggest.py` | 레시피 추천 |
| `parse_receipt.py` | 영수증 이미지 파싱 (OCR) |

**상세 (명령어 예시)**: `{baseDir}/references/usage-examples.md` 참고

## 유통기한 알림

life-coach 스킬의 일일 코칭 리포트에 포함. pantry-manager에서 별도 cron 없음.

## Data Storage

- **DB:** `~/life-dashboard/data.db` → `pantry_items` 테이블
- **캐시:** `~/.cache/pantry-manager/` (이미지 파싱 결과)

## DB Schema

```sql
pantry_items (
    id, name, category, quantity, unit, location,
    purchase_date, expiry_date, status, notes,
    created_at, updated_at,
    UNIQUE(name, location)
)
```

status: '재고 있음' | '부족' | '만료'
