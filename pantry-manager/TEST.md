# Pantry Manager 테스트 가이드

## 설치 확인

### 1. 파일 구조 확인
```bash
cd ~/clawd/skills/pantry-manager
ls -la
```

예상 출력:
- README.md
- SKILL.md
- INSTALL.md
- QUICKSTART.md
- scripts/ (Python 파일들)
- config/ (설정 파일들)

### 2. Python 스크립트 권한 확인
```bash
ls -l scripts/*.py
```

모두 실행 권한 (`-rwxr-xr-x`) 있어야 함.

### 3. Notion API 연결 테스트
```bash
# API 키 확인
cat ~/.config/notion/api_key_daye_personal

# DB ID 설정 확인 (설정했다면)
cat config/notion_db_id.txt
```

## 기능 테스트

### 1. 식재료 추가 테스트
```bash
python3 scripts/add_item.py \
  --name "테스트_당근" \
  --category "채소" \
  --quantity 3 \
  --unit "개" \
  --location "냉장" \
  --expiry "2026-03-01" \
  --notes "설치 테스트"
```

성공 시: `✅ 테스트_당근 추가 완료!`

### 2. 목록 조회 테스트
```bash
python3 scripts/list_items.py
```

방금 추가한 항목이 보여야 함.

### 3. 유통기한 체크 테스트
```bash
python3 scripts/check_expiry.py
```

### 4. 장보기 목록 테스트
```bash
# 먼저 "부족" 상태 아이템 추가 (Notion에서 직접 또는 스크립트 수정)
python3 scripts/shopping_list.py
```

### 5. 주간 리포트 테스트
```bash
python3 scripts/weekly_check.py
```

## 자동화 테스트

### 텔레그램 메시지 전송 테스트
```bash
# 유통기한 체크 → 텔레그램 전송
python3 scripts/check_expiry.py
clawdbot message send -t -1003242721592 --thread-id 167 "$(cat /tmp/pantry_expiry_report.txt)"
```

JARVIS HQ 그룹의 "📅 일정/준비 관련" 토픽에 메시지 도착 확인.

## 정리

### 테스트 데이터 삭제
Notion에서 "테스트_당근" 항목 삭제.

## 문제 발생 시

### 에러: "Notion DB ID 파일이 없습니다"
→ INSTALL.md 2단계 참조하여 DB ID 설정

### 에러: "API 연결 실패"
→ Notion Integration 연결 확인
→ API 키 확인

### 에러: "ModuleNotFoundError"
→ `pip3 install requests` 실행
→ scripts/ 디렉토리에서 실행 확인

## 통합 테스트 (에이전트)

에이전트에게 다음 요청:

1. "양파 5개 추가해줘, 실온, 유통기한 2월 20일"
2. "냉장고에 뭐 있어?"
3. "유통기한 임박한 식재료 알려줘"

모두 정상 동작하면 ✅ 설치 완료!
