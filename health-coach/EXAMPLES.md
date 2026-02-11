# Health Coach - 사용 예시

## 빠른 시작

### 1. 15분 코어 운동 루틴 받기
```bash
python3 ~/clawd/skills/health-coach/scripts/coach.py suggest-routine \
  --duration 15 --focus core --level beginner
```

**출력:**
- 허리디스크 안전한 3-4가지 운동
- 각 운동의 세트/횟수, 호흡법, 주의사항
- 피해야 할 동작 목록
- 안전 원칙

### 2. 운동 자세 상세 가이드
```bash
python3 ~/clawd/skills/health-coach/scripts/coach.py guide-exercise \
  --exercise "플랭크"
```

**출력:**
- 정확한 자세 설명
- 호흡 타이밍
- 흔한 실수
- 난이도 조절 방법

### 3. 수면 자세 조언
```bash
python3 ~/clawd/skills/health-coach/scripts/coach.py lifestyle-advice \
  --category sleep
```

**카테고리:** `sleep`, `diet`, `posture`, `stress`

### 4. 종합 건강 체크
```bash
python3 ~/clawd/skills/health-coach/scripts/coach.py health-checkup
```

**출력:**
- 일일 체크리스트
- 개선 제안

## 대화형 사용 (JARVIS와 대화)

### "오늘 운동 뭐 하지?"
→ `suggest-routine --duration 15 --focus core`

### "플랭크 자세 알려줘"
→ `guide-exercise --exercise "플랭크"`

### "허리 건강한 수면 자세는?"
→ `lifestyle-advice --category sleep`

### "증상 분석해줘"
→ `analyze-symptoms --period 7days` (Notion 연동 후)

## 운동 카테고리

### Core (코어)
- 플랭크, 데드버그, 버드독, 사이드 플랭크, 브리지

### Lower (하체)
- 스쿼트, 런지, 클램쉘

### Flexibility (유연성)
- 캣-카우, 차일드 포즈, 무릎 가슴 당기기

### Cardio (유산소)
- 수영, 걷기, 실내 자전거

## 난이도 레벨

- `beginner` - 초급 (기본 동작, 짧은 시간)
- `intermediate` - 중급 (복잡한 동작, 중간 시간)
- `advanced` - 고급 (도전적인 동작, 긴 시간)

## 라이프스타일 카테고리

### Sleep (수면)
- 수면 자세
- 매트리스/베개 선택
- 수면 환경

### Diet (식단)
- 항염증 식품
- 뼈/근육 건강 영양소
- 수분 섭취

### Posture (자세)
- 앉기, 서기, 들기
- 일상 자세 교정

### Stress (스트레스)
- 호흡법, 명상
- 스트레스 관리 방법

## 안전 원칙

### ✅ 안전한 동작
- 중립척추 유지
- 호흡과 함께 움직이기
- 점진적 강도 증가

### ❌ 피해야 할 동작
- 백 익스텐션 (과신전)
- 싯업 (과도한 굴곡)
- 러시안 트위스트 (회전)
- 레그 레이즈 (허리 아치)

## Health Tracker와 연계

### Tracker → Coach
- Tracker가 증상/운동 데이터 기록
- Coach가 패턴 분석하여 조언

### Coach → Tracker
- Coach가 제안한 운동
- Tracker에 기록하여 추적

## 향후 기능 (예정)

- [ ] Notion Health Log 데이터 실시간 분석
- [ ] Apple Notes PT 숙제 읽어서 가이드
- [ ] 개인화된 루틴 자동 생성
- [ ] 주간 건강 리포트
- [ ] Longevity 스킬 연계 (노화 방지)
