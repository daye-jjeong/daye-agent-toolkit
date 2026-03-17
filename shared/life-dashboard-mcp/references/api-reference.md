# API Reference

## db.py — import 패턴

```python
from db import get_conn, open_conn

# 단순 조회
conn = get_conn()

# 트랜잭션 컨텍스트 (권장)
with open_conn() as conn:
    ...
```

---

## activity_writer.py — CLI 사용

세션 기록·요약·코칭 저장을 담당하는 CLI + 라이브러리. life-coach에서 호출.

```bash
# 미요약 세션 목록
python3 activity_writer.py unsummarized --date 2026-03-16

# 요약 업데이트
python3 activity_writer.py update-summary \
  --session-id <ID> --date 2026-03-16 --tag "코딩" --summary "..."

# 코칭 저장
python3 activity_writer.py save-coaching \
  --date 2026-03-16 --period daily --content "..."

# 태스크 제안 저장
python3 activity_writer.py save-task \
  --date 2026-03-16 --description "..." --priority 1

# 이전 코칭 조회
python3 activity_writer.py previous-coaching --date 2026-03-16

# 태스크 해결
python3 activity_writer.py resolve-task --id 1 --status done --date 2026-03-16

# follow-up 해결
python3 activity_writer.py resolve-followup --id 1 --status resolved --date 2026-03-16
```
