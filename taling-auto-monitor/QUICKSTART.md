# Taling Auto Monitor - 빠른 시작 가이드

## 🚀 5분 설치

### 1단계: Bot Token 받기 (1분)

```bash
# Telegram 앱 열고 @BotFather 검색
# /newbot 명령 입력
# 봇 이름/username 입력
# Token 복사 (예: 123456789:ABCdefGHI...)
```

### 2단계: 환경 변수 설정 (1분)

```bash
# ~/.zshrc 파일에 추가
echo 'export TELEGRAM_BOT_TOKEN="여기에_토큰_붙여넣기"' >> ~/.zshrc
source ~/.zshrc

# 확인
echo $TELEGRAM_BOT_TOKEN
```

### 3단계: Bot을 그룹에 추가 (1분)

```bash
# Telegram JARVIS HQ 그룹 열기
# Members → Add member
# 봇 username 검색 (@your_bot_name)
# 추가 클릭
```

### 4단계: 테스트 (1분)

```bash
cd ~/clawd

# 테스트 실행
./scripts/taling_auto_monitor_v2.py check

# 토픽 168에 테스트 사진 업로드
# (파일명에 "불렛저널" 포함)

# 다시 체크
./scripts/taling_auto_monitor_v2.py check

# 로그 확인 (분류되었는지)
tail logs/taling_auto_monitor.log
```

### 5단계: Cron 설치 (1분)

```bash
# Crontab 열기
crontab -e

# 아래 2줄 복사 붙여넣기
*/10 8-23 * * * /Users/dayejeong/clawd/scripts/taling_auto_monitor_v2.py check >> /Users/dayejeong/clawd/logs/taling_auto_monitor.log 2>&1
0 23 * * * /Users/dayejeong/clawd/scripts/taling_auto_monitor_v2.py report >> /Users/dayejeong/clawd/logs/taling_auto_monitor.log 2>&1

# 저장 (:wq)

# 확인
crontab -l | grep taling
```

## ✅ 완료!

이제 10분마다 자동으로:
- 토픽 168 새 파일 감지
- 7가지 유형 자동 분류
- 누락 파일 즉시 알림
- 23:00 최종 리포트

## 🔍 모니터링

```bash
# 실시간 로그
tail -f logs/taling_auto_monitor.log

# 상태 확인
cat memory/taling_daily_status.json | jq
```

## ⚠️ 문제 해결

### "TELEGRAM_BOT_TOKEN not found"
```bash
# 환경 변수 다시 설정
export TELEGRAM_BOT_TOKEN="your_token"
echo 'export TELEGRAM_BOT_TOKEN="your_token"' >> ~/.zshrc
```

### "No new updates"
- Bot이 그룹에 추가되었는지 확인
- 토픽 168에 테스트 사진 업로드
- 파일명에 키워드 포함 ("불렛저널", "운동" 등)

### 분류 안 됨
파일명이나 캡션에 키워드 포함:
- **불렛저널**: "메모", "할일", "불렛", "todo"
- **침구정리**: "침구", "이불", "정리"
- **지출일기**: "지출", "소비", "일기"
- **저녁운동**: "운동", "전신", "저녁"
- **과제인증**: "과제", "숙제"
- **수강시작**: "시작", "begin"
- **수강종료**: "종료", "완료"

## 📚 더 보기

- **README.md**: 전체 문서
- **SKILL.md**: 아키텍처 설명
- **scripts/taling_auto_monitor_v2.py**: 소스 코드
