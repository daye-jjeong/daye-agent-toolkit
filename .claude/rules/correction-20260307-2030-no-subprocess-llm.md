# 스킬 스크립트에서 LLM subprocess 호출 금지

스킬의 Python/bash 스크립트에서 `claude -p`, `claude --model`, 또는 기타 LLM CLI를 subprocess로 호출하지 마라.

## 올바른 구조

- **Python 스크립트** = 데이터 수집/가공 전용 (DB 조회, API 호출, 파일 파싱)
- **SKILL.md + references/** = LLM이 읽고 적용하는 프레임워크
- **실행 주체** = CC 세션의 LLM 또는 OpenClaw agent가 직접 수행

## cron 자동화

LLM 코칭 없이 템플릿 리포트를 전송한다. LLM 분석이 필요하면 사용자가 온디맨드로 요청.

## 이유

- CC 세션 안에서 nested session 에러
- OpenClaw에서 claude CLI 없음
- 스킬의 온디맨드 패턴과 충돌 (LLM이 직접 해야 할 일을 subprocess가 대신 함)

## 예외: hook 스크립트

`session_logger.py`는 CC hook 스크립트이며 스킬 스크립트가 아니다.
SessionEnd에서의 LLM subprocess 호출(요약 + 행동 추출)은 허용.
이유: hook은 세션 외부에서 실행되며, 데이터 수집 인프라의 일부.
