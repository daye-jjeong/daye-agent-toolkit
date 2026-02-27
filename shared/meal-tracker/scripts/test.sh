#!/bin/bash
# Meal Tracker - 테스트 스크립트

echo "Meal Tracker 테스트 시작..."
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 1. 파일 구조 확인
echo "파일 구조 확인:"
ls -lh "$SCRIPT_DIR/"
ls -lh "$SCRIPT_DIR/../config/"
echo ""

# 2. 영양소 DB 로드 테스트
echo "영양소 DB 테스트:"
python3 -c "
import json
from pathlib import Path
db_path = Path('$SCRIPT_DIR') / '..' / 'config' / 'nutrition_db.json'
with open(db_path.resolve(), 'r', encoding='utf-8') as f:
    db = json.load(f)
print(f'[OK] 카테고리: {len(db)}개')
total_foods = sum(len(foods) for foods in db.values())
print(f'[OK] 음식 항목: {total_foods}개')
"
echo ""

# 3. meals_io 모듈 테스트
echo "meals_io 모듈 테스트:"
python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
import meals_io
print(f'[OK] MEALS_DIR: {meals_io.MEALS_DIR}')
print(f'[OK] today: {meals_io.today()}')
print(f'[OK] now: {meals_io.now()}')
"
echo ""

# 4. Syntax check
echo "구문 검사:"
python3 -m py_compile "$SCRIPT_DIR/meals_io.py" && echo "[OK] meals_io.py"
python3 -m py_compile "$SCRIPT_DIR/log_meal.py" && echo "[OK] log_meal.py"
python3 -m py_compile "$SCRIPT_DIR/daily_summary.py" && echo "[OK] daily_summary.py"
python3 -m py_compile "$SCRIPT_DIR/meal_reminder.py" && echo "[OK] meal_reminder.py"
echo ""

# 5. 식사 기록 테스트
echo "식사 기록 테스트:"
python3 "$SCRIPT_DIR/log_meal.py" \
  --type "점심" \
  --food "닭가슴살, 샐러드, 현미밥" \
  --portion "보통" \
  --notes "테스트 기록"
echo ""

# 6. 거른 식사 테스트
echo "거른 식사 테스트:"
python3 "$SCRIPT_DIR/log_meal.py" \
  --type "저녁" \
  --skipped \
  --notes "입맛 없어서 거름 (테스트)"
echo ""

# 7. Obsidian vault 확인
echo "Obsidian vault 확인:"
vault_dir="$HOME/openclaw/vault/meals"
if [ -d "$vault_dir" ]; then
  echo "[OK] vault 디렉토리 존재: $vault_dir"
  echo "최근 파일:"
  ls -lt "$vault_dir/" | head -5
else
  echo "[!] vault 디렉토리 없음: $vault_dir"
fi
echo ""

echo "테스트 완료!"
