# Worktree Orchestration — Gate 통합 설계

> **Date:** 2026-02-27
> **Status:** Approved (brainstorming 완료)

## 목표

멀티 세션(Warp 8개+) 워크플로우에서 worktree 생명주기를 자동화한다.
별도 스킬/CLI가 아니라 **기존 Gate 시스템에 통합**하여, 사용자는 `claude`만 실행하면 된다.

## 설계 원칙

- 사용자가 직접 호출하는 커맨드는 `wd` (dashboard) 하나뿐
- worktree create/merge/clean은 Claude가 Gate 절차 안에서 자동 실행
- 기존 인프라(session_logger, notify.sh, daily_digest)는 건드리지 않음
- stdlib만 사용 (bash + git), 외부 패키지 금지

## 변경 범위

### 1. Gate 0.5 강화 (`superpowers-workflow-gates.md`)

**현재**: "worktree 쓰세요" 텍스트 규칙만 존재
**변경**: 구체적인 실행 절차 + 스크립트 경로 + closing(merge) 절차 추가

#### Opening (작업 시작시)

```
═══ GATE 0.5: Worktree Isolation ═══
1. worktree.sh create <name> 실행
2. 생성된 worktree로 이동 (EnterWorktree 또는 cd)
3. 메타데이터 기록 (.session-meta.json)
═══════════════════════════════════════
```

#### Closing (작업 완료시, Gate 3 이후)

```
═══ GATE 0.5 CLOSING: Merge & Clean ═══
1. worktree.sh merge <name> 실행
   → backup tag 생성 → main merge → worktree 제거 → branch 삭제
2. 실패시 사용자에게 수동 해결 안내
═══════════════════════════════════════
```

#### Ralph Loop 제안 (Gate 1 실행 중, 태스크별)

subagent-driven-development 실행 중 각 태스크 직전에 Claude가 다음 조건을 **모두** 만족하면 Ralph Loop 전환을 제안한다:
- 명확한 완료 조건이 있음 (테스트 통과, lint 0 에러, 빌드 성공 등)
- 반복 개선이 가능한 작업 (구현 → 테스트 → 수정 사이클)
- 작업 규모가 충분함 (20분+ 소요 예상)

제안 형태:
```
💡 이 태스크는 테스트 기반 완료 조건이 명확합니다.
   Ralph Loop(/ralph-loop)로 전환하면 자율 반복으로 효율적일 수 있습니다.
   전환할까요?
```

**제안만 하고 강제하지 않는다.** 사용자가 거부하면 일반 모드로 진행.

### 2. `_infra/scripts/worktree.sh` (신규)

Claude가 Gate 안에서 호출하는 백엔드 스크립트.

**서브커맨드:**

| 명령 | 설명 |
|------|------|
| `create <name> [description]` | `.claude/worktrees/<name>`에 worktree 생성, branch `wt/<name>`, `.session-meta.json` 기록 |
| `list` | 모든 worktree 상태 출력 (name, branch, changed files, +/-, status) |
| `merge <name>` | backup tag → `git merge --no-ff` → worktree remove → branch delete |
| `clean <name>` | merge 없이 worktree + branch 삭제 (포기할 때) |

**`.session-meta.json` 스키마:**

```json
{
  "name": "feat-auth",
  "description": "인증 기능 구현",
  "created": "2026-02-27T14:30:00+09:00",
  "base_branch": "main",
  "base_sha": "abc1234"
}
```

- worktree 루트에 생성
- `list`와 `wd`가 이 파일을 읽어서 설명 표시
- gitignore 불필요 (worktree 디렉토리 자체가 gitignore됨)

**merge 안전장치:**
- merge 전 `backup/wt-<name>-<timestamp>` 태그 자동 생성
- merge conflict 발생시 abort + 사용자 안내 메시지
- `--dry-run` 옵션으로 사전 확인 가능

### 3. `_infra/cc/wd.sh` (신규)

사용자가 Warp 탭에서 직접 실행하는 유일한 명령.

```bash
wd          # = watch -n 5 "worktree.sh list"
wd --once   # 한번만 출력
```

**출력 포맷:**

```
╔══════════════════════════════════════════════════════════╗
║  worktree dashboard                  (refresh: 5s)      ║
╠══════════════┬────────────┬───────┬────────┬────────────╣
║ Name         │ Branch     │ Files │ +/-    │ Status     ║
╠══════════════╪════════════╪═══════╪════════╪════════════╣
║ feat-auth    │ wt/auth    │    12 │+340/-82│ ● active   ║
║ feat-api     │ wt/api     │     8 │+210/-45│ ● active   ║
║ feat-test    │ wt/test    │     0 │  +0/-0 │ ○ clean    ║
╠══════════════╧════════════╧═══════╧════════╧════════════╣
║ Active: 2/3  │  Total: +550/-127                        ║
╚══════════════════════════════════════════════════════════╝
```

- `● active`: 파일 변경 있음 (git diff --stat > 0)
- `○ clean`: 변경 없음
- Description은 `.session-meta.json`에서 읽기

**설치**: `make install-cc`에서 `~/.local/bin/wd`로 symlink 또는 PATH 안내

### 4. Gate 4 테이블 업데이트

Quick Reference와 Gate 4a 테이블에 closing 단계 추가:

```
All tasks complete → Fresh-Eyes Review   (Gate 3)
Fresh-Eyes Review → Merge worktree       (Gate 0.5 Closing)
```

## 기존 인프라와의 관계

| 기존 컴포넌트 | 영향 | 설명 |
|---|---|---|
| session_logger.py | 없음 | worktree 안에서도 Claude 이벤트가 동일하게 발생 |
| notify.sh | 없음 | 세션 종료 알림 그대로 동작 |
| daily_digest.py | 없음 | 각 세션 로그를 날짜별로 집계 (기존 로직 동일) |
| plan-review-gate.sh | 없음 | worktree 안에서도 docs/plans/ 경로 매칭 동작 |
| finishing-a-development-branch | 대체됨 | Gate 0.5 Closing이 merge 역할을 함 |

## 미래 확장 (현재 구현하지 않음)

- `--ralph` 플래그: Ralph Loop 자동 실행
- `--from-plan`: plan 문서에서 태스크 추출 → worktree 일괄 생성
- Clash 연동: worktree 간 충돌 사전 감지
- 웹 대시보드: `wd --web`으로 HTML 생성 → 모바일 확인
