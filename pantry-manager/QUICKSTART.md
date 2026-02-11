# Pantry Manager 빠른 시작

## 기본 사용법

### 식재료 추가
```bash
python3 scripts/add_item.py \
  --name "양파" \
  --category "채소" \
  --quantity 5 \
  --unit "개" \
  --location "실온" \
  --expiry "2026-02-15"
```

### 유통기한 체크
```bash
python3 scripts/check_expiry.py
```

### 식재료 목록
```bash
# 전체
python3 scripts/list_items.py

# 냉장고만
python3 scripts/list_items.py --location "냉장"

# 채소만
python3 scripts/list_items.py --category "채소"
```

### 장보기 목록
```bash
python3 scripts/shopping_list.py
```

### 레시피 추천
```bash
python3 scripts/recipe_suggest.py
```

### 주간 리포트
```bash
python3 scripts/weekly_check.py
```

## 대화형 사용 (에이전트)

### 추가
- "양파 5개 추가해줘, 실온 보관, 유통기한 2월 15일"
- "우유 1팩 냉장고에 넣었어, 유통기한 2월 10일"

### 조회
- "냉장고에 뭐 있어?"
- "실온에 보관 중인 식재료 알려줘"
- "유통기한 임박한 식재료 체크해줘"

### 레시피
- "오늘 저녁 뭐 만들 수 있어?"
- "현재 재료로 저속노화 메뉴 추천해줘"

### 관리
- "장보기 목록 만들어줘"
- "냉장고 정리 체크해줘"

## 자동 알림 설정

에이전트에게 다음과 같이 요청:

```
매일 아침 9시에 유통기한 체크하고 JARVIS HQ에 알려줘
```

또는

```
주 1회 일요일 저녁에 냉장고 정리 체크 알림 보내줘
```

## 카테고리 & 옵션

### 카테고리
- 채소
- 과일
- 육류
- 가공식품
- 조미료
- 유제품
- 기타

### 단위
- 개
- g
- ml
- 봉지
- 팩

### 위치
- 냉장
- 냉동
- 실온

### 상태
- 재고 있음 (기본)
- 부족
- 만료

## 팁

### 빠른 추가 (기본값 사용)
```bash
# 유통기한 없는 조미료
python3 scripts/add_item.py --name "소금" --category "조미료" --quantity 1 --unit "봉지" --location "실온"
```

### 대량 추가
에이전트에게:
```
다음 항목들 냉장고에 추가해줘:
- 양파 5개 (실온, 2월 15일)
- 당근 10개 (냉장, 2월 20일)
- 우유 2팩 (냉장, 2월 10일)
```

### 영수증으로 추가
```bash
# 1. 영수증 사진 찍기
# 2. 파싱
python3 scripts/parse_receipt.py --image ~/Downloads/receipt.jpg

# 3. 에이전트에게 "이 항목들 냉장고에 추가해줘"
```
