# Pantry Manager Setup Guide

## 1. Notion DB Creation

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

## 2. DB ID Setup

```bash
# Notion에서 Pantry DB 페이지를 열고 URL에서 ID 복사
# https://www.notion.so/YOUR_WORKSPACE/DATABASE_ID?v=...
echo "YOUR_DATABASE_ID" > ~/openclaw/skills/pantry-manager/config/notion_db_id.txt
```

## 3. Python Dependencies

```bash
pip3 install requests pillow pytesseract openai
```

## Troubleshooting

### Notion API Connection Failure
```bash
# API 키 확인
cat ~/.config/notion/api_key_daye_personal

# DB ID 확인
cat ~/openclaw/skills/pantry-manager/config/notion_db_id.txt
```

### Image Recognition Failure
- Tesseract OCR 설치 필요: `brew install tesseract tesseract-lang`
- 한글 인식: `brew install tesseract-lang` (kor 포함)
