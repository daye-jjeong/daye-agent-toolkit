# Pantry Manager Usage Examples

## Script Commands

### Add Item
```bash
python3 {baseDir}/scripts/add_item.py \
  --name "양파" \
  --category "채소" \
  --quantity 5 \
  --unit "개" \
  --location "실온" \
  --expiry "2026-02-15"
```

### List Items
```bash
# 전체 목록
python3 {baseDir}/scripts/list_items.py

# 카테고리별
python3 {baseDir}/scripts/list_items.py --category "채소"

# 위치별
python3 {baseDir}/scripts/list_items.py --location "냉장"

# JSON 출력
python3 {baseDir}/scripts/list_items.py --json
```

### Shopping List
```bash
python3 {baseDir}/scripts/shopping_list.py
```

### Recipe Suggestion
```bash
python3 {baseDir}/scripts/recipe_suggest.py
```

### Receipt Image Parsing
```bash
python3 {baseDir}/scripts/parse_receipt.py --image /path/to/receipt.jpg
```

## 유통기한 알림

life-coach 스킬의 일일 코칭(daily_coach.py)에 포함.
별도 cron 설정 불필요.
