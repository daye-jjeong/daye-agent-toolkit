# Pantry Manager 설치 가이드

## 1. Notion 데이터베이스 생성

1. **Notion에서 새 데이터베이스 생성:**
   - NEW HOME 워크스페이스로 이동
   - 새 페이지 생성 → "Database - Table" 선택
   - 이름: "Pantry" (또는 원하는 이름)

2. **속성 추가:**

   아래 속성들을 차례로 추가하세요:

   | 속성명 | 타입 | 옵션 |
   |--------|------|------|
   | Name | Title | (기본 제공) |
   | Category | Select | 채소, 과일, 육류, 가공식품, 조미료, 유제품, 기타 |
   | Quantity | Number | (숫자) |
   | Unit | Select | 개, g, ml, 봉지, 팩 |
   | Purchase Date | Date | (날짜) |
   | Expiry Date | Date | (날짜) |
   | Location | Select | 냉장, 냉동, 실온 |
   | Status | Select | 재고 있음, 부족, 만료 |
   | Notes | Text | (텍스트) |

3. **Integration 연결:**
   - Notion 페이지 오른쪽 상단 "..." → "Connections" → "Connect to"
   - "Clawdbot" 또는 사용 중인 integration 선택

4. **Database ID 복사:**
   - 브라우저 주소창의 URL 확인
   - 형식: `https://www.notion.so/workspace/DATABASE_ID?v=...`
   - `DATABASE_ID` 부분을 복사

## 2. 로컬 설정

```bash
# DB ID 저장
echo "YOUR_DATABASE_ID" > ~/clawd/skills/pantry-manager/config/notion_db_id.txt

# API 키 확인 (이미 설정되어 있어야 함)
cat ~/.config/notion/api_key_daye_personal
```

## 3. Python 의존성 설치

```bash
# 필수 라이브러리
pip3 install requests

# 이미지 인식 기능 (선택)
pip3 install pillow pytesseract
brew install tesseract tesseract-lang
```

## 4. 테스트

```bash
# 테스트 아이템 추가
python3 ~/clawd/skills/pantry-manager/scripts/add_item.py \
  --name "테스트 양파" \
  --category "채소" \
  --quantity 3 \
  --unit "개" \
  --location "실온" \
  --expiry "2026-02-28"

# 목록 확인
python3 ~/clawd/skills/pantry-manager/scripts/list_items.py
```

## 5. 자동화 설정 (선택)

### Clawdbot Cron 사용 (권장)

```bash
# 매일 아침 9시 유통기한 체크
clawdbot cron add \
  --label "pantry-expiry-check" \
  --schedule "0 9 * * *" \
  --channel -1003242721592 \
  --thread-id 167 \
  --message "유통기한 체크를 실행해줘"

# 매주 일요일 저녁 8시 냉장고 정리 체크
clawdbot cron add \
  --label "pantry-weekly-review" \
  --schedule "0 20 * * 0" \
  --channel -1003242721592 \
  --thread-id 167 \
  --message "냉장고 정리 체크를 실행해줘"
```

### 시스템 Cron 사용

```bash
# crontab 편집
crontab -e

# 아래 라인 추가:
0 9 * * * cd ~/clawd && python3 skills/pantry-manager/scripts/check_expiry.py && clawdbot message send -t -1003242721592 --thread-id 167 "$(cat /tmp/pantry_expiry_report.txt)"
0 20 * * 0 cd ~/clawd && python3 skills/pantry-manager/scripts/weekly_check.py && clawdbot message send -t -1003242721592 --thread-id 167 "$(cat /tmp/pantry_weekly_report.txt)"
```

## 6. 에이전트와 연동

이제 에이전트에게 다음과 같이 요청할 수 있습니다:

- "양파 5개 추가해줘"
- "유통기한 임박한 식재료 알려줘"
- "냉장고에 뭐 있어?"
- "오늘 저녁 뭐 만들 수 있어?"

## 문제 해결

### "Notion API 연결 실패"
```bash
# API 키 확인
cat ~/.config/notion/api_key_daye_personal

# DB ID 확인
cat ~/clawd/skills/pantry-manager/config/notion_db_id.txt
```

### "ModuleNotFoundError: notion_client"
```bash
# Python path 확인
cd ~/clawd/skills/pantry-manager/scripts
python3 -c "import sys; print(sys.path)"

# 스크립트를 scripts/ 디렉토리 내에서 실행하세요
```

### "Tesseract not found"
```bash
# Tesseract 설치
brew install tesseract tesseract-lang

# 설치 확인
tesseract --version
```
