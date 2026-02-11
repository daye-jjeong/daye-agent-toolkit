# Pantry Manager Skill


**Version:** 0.1.0
**Updated:** 2026-02-03
**Compatibility:** Clawdbot >= 1.0.0
**Status:** Experimental

식재료 관리 자동화 스킬.

## 설치 & 설정

### 1. Notion DB 생성

**NEW HOME 워크스페이스**에 "Pantry" 데이터베이스를 생성하고 다음 속성을 추가:

| 속성명 | 타입 | 옵션 |
|--------|------|------|
| Name | Title | 식재료명 |
| Category | Select | 채소, 과일, 육류, 가공식품, 조미료, 유제품, 기타 |
| Quantity | Number | 수량 |
| Unit | Select | 개, g, ml, 봉지, 팩 |
| Purchase Date | Date | 구매일 |
| Expiry Date | Date | 유통기한 |
| Location | Select | 냉장, 냉동, 실온 |
| Status | Select | 재고 있음, 부족, 만료 |
| Notes | Text | 메모 |

### 2. DB ID 설정

```bash
# Notion에서 Pantry DB 페이지를 열고 URL에서 ID 복사
# https://www.notion.so/YOUR_WORKSPACE/DATABASE_ID?v=...
echo "YOUR_DATABASE_ID" > ~/clawd/skills/pantry-manager/config/notion_db_id.txt
```

### 3. Python 의존성 설치

```bash
pip3 install requests pillow pytesseract openai
```

## 사용법

### 식재료 추가

```bash
python3 ~/clawd/skills/pantry-manager/scripts/add_item.py \
  --name "양파" \
  --category "채소" \
  --quantity 5 \
  --unit "개" \
  --location "실온" \
  --expiry "2026-02-15"
```

### 유통기한 체크

```bash
# 임박(3일 이내) + 만료 식재료 확인
python3 ~/clawd/skills/pantry-manager/scripts/check_expiry.py
```

### 식재료 목록 조회

```bash
# 전체 목록
python3 ~/clawd/skills/pantry-manager/scripts/list_items.py

# 카테고리별
python3 ~/clawd/skills/pantry-manager/scripts/list_items.py --category "채소"

# 위치별
python3 ~/clawd/skills/pantry-manager/scripts/list_items.py --location "냉장"
```

### 장보기 목록 생성

```bash
python3 ~/clawd/skills/pantry-manager/scripts/shopping_list.py
```

### 레시피 추천

```bash
# 현재 재료로 만들 수 있는 저속노화 메뉴
python3 ~/clawd/skills/pantry-manager/scripts/recipe_suggest.py
```

### 이미지 인식 (장바구니 파싱)

```bash
python3 ~/clawd/skills/pantry-manager/scripts/parse_receipt.py --image /path/to/receipt.jpg
```

## 자동화 설정

### Cron 설정

```bash
# 매일 아침 9시 유통기한 체크
0 9 * * * cd ~/clawd && python3 skills/pantry-manager/scripts/check_expiry.py && clawdbot message send -t -1003242721592 --thread-id 167 "$(cat /tmp/pantry_expiry_report.txt)"

# 매주 일요일 저녁 8시 냉장고 정리 체크
0 20 * * 0 cd ~/clawd && python3 skills/pantry-manager/scripts/weekly_check.py && clawdbot message send -t -1003242721592 --thread-id 167 "$(cat /tmp/pantry_weekly_report.txt)"
```

또는 Clawdbot 내장 cron 사용:

```bash
clawdbot cron add \
  --label "pantry-expiry-check" \
  --schedule "0 9 * * *" \
  --channel -1003242721592 \
  --message "유통기한 체크를 실행해줘"

clawdbot cron add \
  --label "pantry-weekly-review" \
  --schedule "0 20 * * 0" \
  --channel -1003242721592 \
  --message "냉장고 정리 체크를 실행해줘"
```

## 대화형 사용

에이전트에게 다음과 같이 요청할 수 있습니다:

- "양파 5개 추가해줘, 유통기한 2월 15일"
- "유통기한 임박한 식재료 알려줘"
- "냉장고에 뭐 있어?"
- "오늘 저녁 뭐 만들 수 있어?"
- "장보기 목록 만들어줘"
- "영수증 사진으로 식재료 추가해줘" (이미지 첨부)

## API 키

- **Notion API:** `~/.config/notion/api_key_daye_personal` (NEW HOME 워크스페이스)
- **OpenAI API:** (레시피 추천 및 이미지 파싱용) 시스템 환경변수 사용

## 데이터 저장

- **Notion DB:** 모든 식재료 데이터
- **로컬 캐시:** `~/.cache/pantry-manager/` (임시 리포트, 이미지 파싱 결과)

## 트러블슈팅

### Notion API 연결 실패
```bash
# API 키 확인
cat ~/.config/notion/api_key_daye_personal

# DB ID 확인
cat ~/clawd/skills/pantry-manager/config/notion_db_id.txt
```

### 이미지 인식 실패
- Tesseract OCR 설치 필요: `brew install tesseract tesseract-lang`
- 한글 인식: `brew install tesseract-lang` (kor 포함)
