# Pantry Manager Usage Examples

## Script Commands

### Add Item
```bash
python3 ~/openclaw/skills/pantry-manager/scripts/add_item.py \
  --name "양파" \
  --category "채소" \
  --quantity 5 \
  --unit "개" \
  --location "실온" \
  --expiry "2026-02-15"
```

### Check Expiry
```bash
# 임박(3일 이내) + 만료 식재료 확인
python3 ~/openclaw/skills/pantry-manager/scripts/check_expiry.py
```

### List Items
```bash
# 전체 목록
python3 ~/openclaw/skills/pantry-manager/scripts/list_items.py

# 카테고리별
python3 ~/openclaw/skills/pantry-manager/scripts/list_items.py --category "채소"

# 위치별
python3 ~/openclaw/skills/pantry-manager/scripts/list_items.py --location "냉장"
```

### Shopping List
```bash
python3 ~/openclaw/skills/pantry-manager/scripts/shopping_list.py
```

### Recipe Suggestion
```bash
# 현재 재료로 만들 수 있는 저속노화 메뉴
python3 ~/openclaw/skills/pantry-manager/scripts/recipe_suggest.py
```

### Receipt Image Parsing
```bash
python3 ~/openclaw/skills/pantry-manager/scripts/parse_receipt.py --image /path/to/receipt.jpg
```

## Cron Setup

```bash
# 매일 아침 9시 유통기한 체크
0 9 * * * cd ~/clawd && python3 skills/pantry-manager/scripts/check_expiry.py && clawdbot message send -t -1003242721592 --thread-id 167 "$(cat /tmp/pantry_expiry_report.txt)"

# 매주 일요일 저녁 8시 냉장고 정리 체크
0 20 * * 0 cd ~/clawd && python3 skills/pantry-manager/scripts/weekly_check.py && clawdbot message send -t -1003242721592 --thread-id 167 "$(cat /tmp/pantry_weekly_report.txt)"
```

Or via Clawdbot built-in cron:

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
