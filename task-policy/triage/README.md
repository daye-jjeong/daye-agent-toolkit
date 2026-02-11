# Task Policy Triage - Task 관리 개선 (2026-02-05)

**목적:** Notion Tasks DB를 anthropic TASKS.md 스타일로 운영 가능하게 개선

## 📦 구성 요소

### 1. Task 생성 로직 (`triage.py`)
**개선사항:**
- ✅ **Owner 기본값 강제:** 모든 Task에 "다예" 자동 할당
- ✅ **Priority 기본값:** P2 (누락 시에만 채움)
- ✅ **Start Date 정책 준수:** 작업 시작 시에만 설정 (생성 시에는 설정 안 함)
- ✅ **Status 일관성:** "Not Started" 기본값

**사용법:**
```bash
# Dry-run (미리보기)
python3 triage.py "Clawdbot 가이드 작성"

# 실제 생성
python3 triage.py "Clawdbot 가이드 작성" --execute

# Epic/Project 강제 지정
python3 triage.py "로닉 키오스크 연동" --override-classification Project
```

### 2. Task 속성 헬퍼 (`task_helpers.py`)
**기능:**
- `set_task_start_date()` - 작업 시작 시 Start Date 자동 설정
- `set_task_owner()` - Owner 설정
- `set_task_priority()` - Priority 설정 (기존 값 보존)
- `ensure_task_defaults()` - 필수 속성 일괄 설정

**사용 예시:**
```python
from skills.task_policy.triage.task_helpers import ensure_task_defaults

# Task 시작 시 (서브에이전트에서)
result = ensure_task_defaults(
    task_id="abc123",
    owner="다예",
    priority="P2",
    set_start_date=True  # 작업 시작하니까 Start Date 설정
)
```

### 3. Automation Logger (`automation_logger.py`)
**목적:** 크론 작업 실행 흔적을 Notion에 자동 기록

**특징:**
- 🤖 **중앙 집중형:** 단일 "Automation Logs (System)" Task에 모든 로그 누적
- ✅ **중복 방지:** 시간순으로 추가만 (덮어쓰기 없음)
- 📊 **구조화된 로그:** 실행 시각, 성공/실패, 메시지 ID, 메타데이터

**사용 예시:**
```python
from skills.task_policy.triage.automation_logger import log_automation_run

# 크론 작업 시작 시
try:
    result = send_morning_brief()
    
    # 성공 로그
    log_automation_run(
        automation_name="Morning Brief",
        status="success",
        summary="아침 브리프 전송 (일정 3개, 날씨)",
        message_id=result["message_id"]
    )
except Exception as e:
    # 실패 로그
    log_automation_run(
        automation_name="Morning Brief",
        status="failure",
        summary="전송 실패",
        error=str(e)
    )
```

**CLI 사용:**
```bash
# 로그 추가
python3 automation_logger.py log "Morning Brief" success "브리프 전송 완료" --message-id 12345

# 최근 로그 확인
python3 automation_logger.py list --limit 10
```

### 4. Notion 뷰 설정 (`notion_view_setup.py` + 가이드)
**출력:** `NOTION_VIEW_GUIDE.md` - TASKS.md 스타일 Board 뷰 설정 가이드

**주요 내용:**
- Status → Category 매핑 (Active/Waiting On/Someday/Done)
- Board 뷰 생성 단계별 가이드
- 필터/정렬/그룹화 설정
- 일일/주간 운영 루틴
- 자동화 통합 방법

## 🚀 통합 워크플로우

### Agent가 Task 생성할 때
```python
# 1. Task 생성 (기본값 자동 설정)
from skills.task_policy.triage.triage import handle_user_request

result = handle_user_request("Clawdbot 가이드 작성", auto_approve=True)
task_id = result["notion_entry"]["id"]
task_url = result["notion_entry"]["url"]

# 2. 작업 시작 시 Start Date 설정
from skills.task_policy.triage.task_helpers import set_task_start_date
set_task_start_date(task_id)

# 3. 작업 완료 시 Status 업데이트
notion.pages.update(task_id, properties={
    "Status": {"status": {"name": "Done"}}
})
```

### 크론 작업 통합
```python
#!/usr/bin/env python3
from skills.task_policy.triage.automation_logger import log_automation_run

def morning_brief_cron():
    automation_name = "Morning Brief"
    
    try:
        # 기존 로직
        result = generate_and_send_brief()
        
        # Notion 로그 기록
        log_automation_run(
            automation_name=automation_name,
            status="success",
            summary=f"브리프 전송 (항목 {result['count']}개)",
            message_id=result["message_id"],
            metadata={"target": "JARVIS HQ", "topic_id": 167}
        )
        
    except Exception as e:
        # 실패 로그
        log_automation_run(
            automation_name=automation_name,
            status="failure",
            summary="브리프 생성 실패",
            error=str(e)
        )
        raise
```

## 📋 마이그레이션 체크리스트

### A) Task 생성 로직 개선 ✅
- [x] `triage.py`: Owner 기본값 강제
- [x] `triage.py`: Priority 기본값 (P2)
- [x] `triage.py`: Start Date 정책 준수 (생성 시 미설정)
- [x] `task_helpers.py`: 작업 시작 시 Start Date 자동 설정 함수

### B) 자동화 실행 로그 ✅
- [x] `automation_logger.py`: 중앙 로그 Task 생성
- [x] 로그 기록 함수 (`log_automation_run`)
- [x] 중복 방지 (시간순 추가)
- [x] CLI 인터페이스
- [x] `AUTOMATION_INTEGRATION.md`: 통합 가이드

### C) Notion 뷰 개선 ✅
- [x] `notion_view_setup.py`: DB 분석 스크립트
- [x] `NOTION_VIEW_GUIDE.md`: TASKS.md 스타일 설정 가이드
- [x] Status → Category 매핑 정의
- [x] 일일/주간 운영 루틴 문서화

## 🔧 다음 단계 (선택사항)

### 즉시 적용 가능
1. **Notion에서 Board 뷰 생성** - `NOTION_VIEW_GUIDE.md` 참고 (5분)
2. **Automation Log Task 생성** - 아무 크론이나 1번 실행하면 자동 생성
3. **기존 Task 속성 보정** - Owner/Priority 누락된 것 일괄 수정

### 점진적 통합 (1-2주)
1. **크론 작업 로깅 추가** - 우선순위: Morning Brief, Stock Report
2. **Agent 코드 업데이트** - Task 시작 시 `set_task_start_date()` 호출
3. **Template 적용** - 새 Task 생성 시 body 템플릿 자동 삽입

### 장기 개선 (1개월+)
1. **자동화 대시보드** - Automation Log 통계 뷰
2. **Status 자동 전환** - Start Date 설정 시 → Active
3. **Due 알림** - 마감 1일 전 Telegram 알림
4. **Weekly 회고 자동화** - 금요일 저녁 완료 작업 요약

## 📚 관련 문서
- **AGENTS.md § 7** - Task-Centric Policy
- **POLICY.md** - Task Policy Operating Rules
- **AUTOMATION_INTEGRATION.md** - 크론 작업 통합 가이드
- **NOTION_VIEW_GUIDE.md** - Board 뷰 설정 가이드

## 🆘 지원
- **로그 확인:** `~/.config/notion/automation_log_task_id`
- **API Key:** `~/.config/notion/api_key_daye_personal`
- **Tasks DB:** `8e0e8902-0c60-4438-8bbf-abe10d474b9b`
