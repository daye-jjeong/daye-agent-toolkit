---
name: pantry-manager
description: 식재료 관리 자동화 — 재고, 유통기한, 쇼핑리스트, 레시피 추천
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Pantry Manager Skill

**Version:** 0.1.0 | **Updated:** 2026-02-03 | **Status:** Experimental

식재료 관리 자동화 스킬. Notion DB 기반 재고 관리, 유통기한 알림, 장보기 목록, 레시피 추천.

## 트리거

사용자가 다음을 요청할 때 활성화:
- "양파 5개 추가해줘, 유통기한 2월 15일"
- "유통기한 임박한 식재료 알려줘"
- "냉장고에 뭐 있어?"
- "오늘 저녁 뭐 만들 수 있어?"
- "장보기 목록 만들어줘"
- "영수증 사진으로 식재료 추가해줘" (이미지 첨부)

## 설치 & 설정

Notion DB(Pantry) 생성 + API 키 + Python 의존성 필요.

**상세**: `{baseDir}/references/setup-guide.md` 참고

## Core Workflow

1. **추가**: 식재료 정보를 Notion DB에 등록 (이름, 카테고리, 수량, 유통기한, 위치)
2. **조회**: 전체/카테고리별/위치별 식재료 목록 조회
3. **유통기한 체크**: 임박(3일 이내) + 만료 식재료 알림
4. **장보기 목록**: 부족/만료 항목 기반 자동 생성
5. **레시피 추천**: 현재 재고 기반 저속노화 메뉴 추천
6. **이미지 파싱**: 영수증 사진에서 식재료 자동 추출 (OCR)

## Scripts

| Script | Purpose |
|--------|---------|
| `add_item.py` | 식재료 추가 |
| `list_items.py` | 목록 조회 (--category, --location) |
| `check_expiry.py` | 유통기한 체크 |
| `shopping_list.py` | 장보기 목록 생성 |
| `recipe_suggest.py` | 레시피 추천 |
| `parse_receipt.py` | 영수증 이미지 파싱 |

**상세 (명령어 예시, 크론 설정)**: `{baseDir}/references/usage-examples.md` 참고

## 자동화

- 매일 09:00: 유통기한 체크 -> Telegram 알림
- 매주 일 20:00: 냉장고 정리 체크 -> Telegram 알림

## API Keys

- **Notion API:** `~/.config/notion/api_key_daye_personal` (NEW HOME)
- **OpenAI API:** 시스템 환경변수 (레시피 추천 + 이미지 파싱용)

## Data Storage

- **Notion DB:** 모든 식재료 데이터
- **로컬 캐시:** `~/.cache/pantry-manager/` (임시 리포트, 이미지 파싱 결과)
