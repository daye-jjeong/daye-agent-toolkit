## Design

### 목표
세션 데이터에 branch 필드 추가 + 요약 프롬프트 개선 + 레포>태스크 2단계 그룹핑

### 데이터 흐름
```
session_logger.py (hook) → work-log/*.md → parse_work_log.py → sync_cc.py → SQLite activities → daily_coach.py → daily_report.py (HTML)
```

branch 정보가 이 파이프라인 전체를 관통해야 한다.

### branch 기록 형식
work-log 마크다운에 `**브랜치**: wt/feature-x` 줄 추가 (기존 `**주제**:`, `**요약**:` 패턴과 일치)

---

## Tasks

- [x] T1 ✅: session_logger.py — detect_repo() → detect_repo_and_branch() + 마크다운에 branch 기록
- [x] T2: session_logger.py — LLM 요약 프롬프트 개선 (프로세스 생략, 결과물만)
- [x] T3: parse_work_log.py — **브랜치**: 줄 파싱 + session dict에 branch 필드
- [x] T4: schema.sql + db.py + sync_cc.py — activities 테이블 branch 컬럼 추가
- [x] T5: daily_coach.py — activities 쿼리에 branch 포함, 텔레그램 리포트 2단계 그룹핑
- [x] T6: daily_report.py — HTML 레포>branch 2단계 그룹핑
