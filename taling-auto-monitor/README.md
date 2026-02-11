# Taling Challenge Auto Monitor

**Type:** Tier 1 Script (Pure Code)  
**Architecture:** Telegram Bot API + State tracker + Clawdbot alerts

## Overview

자동으로 JARVIS HQ 토픽 168 (탈잉 챌린지)의 파일 업로드를 감지하고, 요일별 체크리스트를 추적합니다. 누락 파일 즉시 알림, 23:00 최종 독려 메시지 발송.

## Key Features

- ✅ **자동 감지**: 별도 "체크해줘" 명령 불필요
- 🗂️ **파일 분류**: 7가지 파일 유형 자동 분류
- 📅 **요일별 체크리스트**: 월수금 8개, 화목토일 4개
- ⏰ **데드라인 알림**: 23:00 최종 리포트
- 🔄 **지속적 추적**: 10분마다 상태 체크

## Architecture

```
┌─────────────────────────────────┐
│ Telegram Bot API (getUpdates)   │
│ • Topic 168 messages            │
│ • File uploads (photo/document) │
│ • Text messages (학습후기)       │
└────────────┬────────────────────┘
             │ JSON (updates)
             ▼
┌─────────────────────────────────┐
│ scripts/taling_auto_monitor_v2  │ ← 0 tokens
│ • Parse topic 168 messages      │
│ • Classify files (pattern match)│
│ • Track daily state             │
│ • Send alerts (via clawdbot)    │
└────────────┬────────────────────┘
             │ JSON
             ▼
┌─────────────────────────────────┐
│ memory/taling_daily_status.json │
│ • last_update_id (offset)       │
│ • daily_files                   │
│ • daily_reviews                 │
└─────────────────────────────────┘
             │ Alerts
             ▼
┌─────────────────────────────────┐
│ clawdbot message send           │
│ → Telegram topic 168            │
└─────────────────────────────────┘
```

## File Classification

### Patterns
- **수강시작**: "시작", "start", "begin"
- **수강종료**: "종료", "end", "finish", "완료"
- **과제인증**: "과제", "assignment", "homework", "숙제"
- **불렛저널**: "메모", "할일", "불렛", "bullet", "journal", "todo"
- **침구정리**: "침구", "이불", "정리", "bed", "bedding"
- **지출일기**: "지출", "소비", "일기", "expense", "spending"
- **저녁운동**: "운동", "전신", "저녁", "workout", "exercise", "evening"

### Requirements by Day

**월수금 (8개 항목):**
1. 수강시작 (사진)
2. 수강종료 (사진)
3. 과제인증 (사진)
4. 불렛저널 (사진)
5. 침구정리 (사진)
6. 지출일기 (사진)
7. 저녁운동 (사진)
8. **학습후기 500자** (텍스트 메시지)

**화목토일 (4개 항목):**
1. 불렛저널 (사진)
2. 침구정리 (사진)
3. 지출일기 (사진)
4. 저녁운동 (사진)

## Setup

### 1. Get Telegram Bot Token

```bash
# 1. Message @BotFather on Telegram
# 2. Create new bot: /newbot
# 3. Follow instructions, get token like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# 4. Export token (add to ~/.zshrc for persistence)
echo 'export TELEGRAM_BOT_TOKEN="your_token_here"' >> ~/.zshrc
source ~/.zshrc

# Verify
echo $TELEGRAM_BOT_TOKEN
```

### 2. Test Manually

```bash
# Check for new messages (should work immediately)
./scripts/taling_auto_monitor_v2.py check

# Send test report
./scripts/taling_auto_monitor_v2.py report

# Reset today's state (testing only)
./scripts/taling_auto_monitor_v2.py reset
```

### 3. Install Cron Jobs

```bash
# Edit crontab
crontab -e

# Add these lines (paste from skills/taling-auto-monitor/cron_config.txt):
*/10 8-23 * * * /Users/dayejeong/clawd/scripts/taling_auto_monitor_v2.py check >> /Users/dayejeong/clawd/logs/taling_auto_monitor.log 2>&1
0 23 * * * /Users/dayejeong/clawd/scripts/taling_auto_monitor_v2.py report >> /Users/dayejeong/clawd/logs/taling_auto_monitor.log 2>&1

# Verify
crontab -l | grep taling
```

### 4. Monitor Logs

```bash
# Watch logs in real-time
tail -f logs/taling_auto_monitor.log

# Check recent activity
tail -50 logs/taling_auto_monitor.log
```

## State File Structure

**Location:** `memory/taling_daily_status.json`

```json
{
  "last_update_id": 987654321,
  "daily_files": {
    "2026-02-02": [
      {
        "type": "불렛저널",
        "filename": "메모_20260202.jpg",
        "timestamp": "2026-02-02T09:15:00+09:00"
      }
    ]
  },
  "daily_reviews": {
    "2026-02-02": "학습후기 500자 이상..."
  }
}
```

## Alert Examples

### File Upload Detected
```
✅ Classified: 메모_20260202.jpg → 불렛저널

📊 탈잉 챌린지 진행 상황 (월수금)
✅ 완료: 불렛저널
❌ 누락: 수강시작, 수강종료, 과제인증, 침구정리, 지출일기, 저녁운동
```

### All Files Complete
```
🎉 탈잉 챌린지 파일 업로드 완료!
날짜: 2026-02-02 (월수금)
업로드: 과제인증, 불렛저널, 수강시작, 수강종료, 저녁운동, 지출일기, 침구정리

⚠️ 학습후기 500자 작성 잊지 마세요!
```

### Review Text Check
```
✅ 학습후기 확인됨
글자 수: 523자 (500자 이상 완료)
```

### Final Report (23:00)
```
⚠️ 탈잉 챌린지 2026-02-02 마감 임박! (23:59)

📋 월수금 체크리스트:
✅ 수강시작
✅ 수강종료
❌ 과제인증 ⚠️
✅ 불렛저널
✅ 침구정리
✅ 지출일기
✅ 저녁운동
❌ 학습후기 500자 ⚠️

⏰ 마감까지 56분!
지금 바로 업로드하세요! 🏃‍♀️
```

## Important Notes

### Challenge Rules
- **기간**: 2개월 (60일)
- **보상**: 10만원 (모든 날짜 완료 시)
- **데드라인**: 매일 23:59
- **누락 시**: 패널티 (전액 환불 없음)

### Monitoring
- **Check interval**: 10분 (8 AM - 11 PM)
- **Final reminder**: 23:00 (1시간 전)
- **Log location**: `logs/taling_auto_monitor.log`

### Troubleshooting

**"TELEGRAM_BOT_TOKEN not found" 오류:**
```bash
# 환경 변수 확인
echo $TELEGRAM_BOT_TOKEN

# 없으면 다시 설정
export TELEGRAM_BOT_TOKEN="your_token"
echo 'export TELEGRAM_BOT_TOKEN="your_token"' >> ~/.zshrc
```

**"No new updates" 계속 뜨는 경우:**
```bash
# Bot이 group에 추가되었는지 확인
# 1. Telegram에서 JARVIS HQ 그룹 열기
# 2. Add member → 봇 검색 → 추가
# 3. 토픽 168에 테스트 사진 업로드

# 상태 파일 확인
cat memory/taling_daily_status.json

# last_update_id 리셋 (모든 메시지 다시 처리)
# memory/taling_daily_status.json 에서 last_update_id: 0 으로 변경
```

**분류가 안 되는 경우:**
```bash
# 파일명 패턴 확인
# 파일명이나 캡션에 키워드 포함되어야 함
# 예: "불렛저널_20260202.jpg", "메모", "할일"

# 패턴 목록은 FILE_PATTERNS 참고
# scripts/taling_auto_monitor_v2.py:35-42
```

**로그 확인:**
```bash
# 최근 로그
tail -50 logs/taling_auto_monitor.log

# 실시간 모니터링
tail -f logs/taling_auto_monitor.log

# 오류만 필터
grep "❌" logs/taling_auto_monitor.log
```

## Migration from Old System

**기존 시스템 (taling_monitor.py):**
- Telegram Bot API polling 방식
- 별도 Bot 프로세스 필요
- 실시간 감지하지만 자원 소모

**새 시스템 (taling_auto_monitor.py):**
- Clawdbot 메시지 백업 활용
- Cron 기반 정기 체크
- 통합된 시스템, 자원 효율적

**병렬 운영 가능:**
- 두 시스템은 상태 파일이 다름
- 필요 시 기존 시스템 유지 가능
- 2주 테스트 후 기존 시스템 종료 권장

## See Also

- **AGENTS.md**: Three-tier architecture policy
- **scripts/taling_monitor.py**: Legacy polling-based monitor
- **TOOLS.md**: Telegram topic IDs and configuration
