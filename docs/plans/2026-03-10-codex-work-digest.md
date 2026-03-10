# Codex Work Digest Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Codex-specific work-digest automation that sends Telegram notifications for completion or user-confirmation turns and writes markdown work logs on compaction and session end.

**Architecture:** Codex CLI is wrapped by `codex-wrapper.sh`, which discovers the session JSONL, watches for compaction events, and invokes `session_logger.py` on compaction and process exit. `notify.sh` is wired via `~/.codex/config.toml` for real-time approval and turn-complete notifications. Logs are written under `codex/work-digest/work-log/`.

**Tech Stack:** Bash, Python 3 stdlib, Codex CLI (`codex exec --ephemeral` for summarization), zsh shell config

**Design doc:** `docs/plans/2026-03-10-codex-work-digest-design.md`

---

### Task 1: Scaffold Codex work-digest module

**Files:**
- Create: `codex/work-digest/.gitignore`
- Create: `codex/work-digest/work-log/.gitkeep`
- Create: `codex/work-digest/state/.gitkeep`
- Create: `codex/work-digest/tests/fixtures/.gitkeep`

**Step 1: Create the directory tree**

Run:

```bash
mkdir -p codex/work-digest/scripts codex/work-digest/state codex/work-digest/work-log codex/work-digest/tests/fixtures
```

Expected:
- Directories exist under `codex/work-digest/`

**Step 2: Add ignore rules for local log/state data**

Write `codex/work-digest/.gitignore`:

```gitignore
work-log/*.md
state/*.json
tests/tmp/
telegram.conf
```

Keep `.gitkeep` files tracked so the directories remain in git.

**Step 3: Verify only placeholders are tracked**

Run:

```bash
git status --short codex/work-digest
```

Expected:
- Only `.gitignore` and `.gitkeep` files appear as new files

**Step 4: Commit**

```bash
git add codex/work-digest/.gitignore codex/work-digest/work-log/.gitkeep codex/work-digest/state/.gitkeep codex/work-digest/tests/fixtures/.gitkeep
git commit -m "feat(codex-work-digest): scaffold codex work digest directories"
```

---

### Task 2: Session logger tests and fixtures

**Files:**
- Create: `codex/work-digest/tests/fixtures/session_end.jsonl`
- Create: `codex/work-digest/tests/fixtures/compaction.jsonl`
- Create: `codex/work-digest/tests/test_session_logger.py`

**Step 1: Create fixture transcript for session end**

Build `session_end.jsonl` with realistic Codex events:
- `session_meta`
- `turn_context`
- `event_msg.user_message`
- `response_item.function_call`
- `response_item.function_call_output`
- `event_msg.token_count`
- `event_msg.task_complete`

Fixture requirements:
- include `cwd`
- include one command execution
- include one final `task_complete.last_agent_message`
- include token totals

**Step 2: Create fixture transcript for compaction**

Build `compaction.jsonl` with:
- normal conversation entries
- one `compacted` row with `replacement_history`
- one `event_msg` with `type: context_compacted`

**Step 3: Write the failing tests**

Create `test_session_logger.py` with `unittest` coverage for:

```python
def test_parse_transcript_extracts_topic_commands_tokens(): ...
def test_parse_transcript_tracks_task_complete_message(): ...
def test_extract_compaction_summary_uses_replacement_history(): ...
def test_build_session_section_marks_source_and_event(): ...
def test_already_recorded_blocks_duplicate_event(): ...
def test_summarize_session_uses_real_codex_binary_path(): ...
```

Mock `subprocess.run` for summarization tests so no network call happens in unit tests.

**Step 4: Run the tests to confirm RED**

Run:

```bash
python3 -m unittest discover -s codex/work-digest/tests -p 'test_session_logger.py' -v
```

Expected:
- FAIL with import or missing function errors for `session_logger.py`

**Step 5: Commit**

```bash
git add codex/work-digest/tests/fixtures/session_end.jsonl codex/work-digest/tests/fixtures/compaction.jsonl codex/work-digest/tests/test_session_logger.py
git commit -m "test(codex-work-digest): add session logger fixtures and failing tests"
```

---

### Task 3: Implement `_common.py` and `session_logger.py`

**Files:**
- Create: `codex/work-digest/scripts/_common.py`
- Create: `codex/work-digest/scripts/session_logger.py`
- Test: `codex/work-digest/tests/test_session_logger.py`

**Step 1: Implement `_common.py`**

Add:
- `BASE_DIR = Path(__file__).resolve().parent.parent`
- `TELEGRAM_CONF = BASE_DIR / "telegram.conf"`
- fallback config path:
  `Path(__file__).resolve().parents[3] / "cc/work-digest/telegram.conf"`
- `WEEKDAYS_KO`
- `WORK_TAGS`
- `format_tokens()`
- `load_telegram_conf()`
- `send_telegram()`

The fallback keeps one Telegram config source by default while still allowing a Codex-local override later.

**Step 2: Implement transcript parsing**

In `session_logger.py`, add:
- `parse_transcript(transcript_path) -> dict`
- `extract_conversation(transcript_path) -> str`
- `extract_compaction_text(transcript_path) -> str`
- `detect_repo(cwd) -> str`
- state helpers mirroring Claude logic

Data to extract:
- session start/end
- topic
- last agent message
- task complete message
- command count / recent commands
- token usage
- approval count
- compaction flag

**Step 3: Implement compaction and session_end formatting**

Add:
- `build_frontmatter(now)`
- `build_session_section(session_id, data, now, repo, event)`
- `write_session_marker(...)`

Section requirements:
- frontmatter includes `source: codex`
- section includes `> source: codex | event: compaction|session_end`
- compaction uses short replacement-history based summary

**Step 4: Implement final summarization via real Codex binary**

Add `summarize_session()` that runs:

```bash
/opt/homebrew/bin/codex exec --ephemeral -C <cwd> "<prompt>"
```

Requirements:
- never call wrapper path
- handle timeout and missing binary gracefully
- parse `[태그]\n요약` response
- only run on `session_end`

**Step 5: Run the targeted tests to confirm GREEN**

Run:

```bash
python3 -m unittest discover -s codex/work-digest/tests -p 'test_session_logger.py' -v
```

Expected:
- PASS

**Step 6: Run a syntax check**

Run:

```bash
python3 -m py_compile codex/work-digest/scripts/_common.py codex/work-digest/scripts/session_logger.py
```

Expected:
- no output

**Step 7: Commit**

```bash
git add codex/work-digest/scripts/_common.py codex/work-digest/scripts/session_logger.py
git commit -m "feat(codex-work-digest): implement codex session logger"
```

---

### Task 4: Notify tests with dry-run behavior

**Files:**
- Create: `codex/work-digest/tests/fixtures/notify-approval-requested.json`
- Create: `codex/work-digest/tests/fixtures/notify-turn-complete-finished.json`
- Create: `codex/work-digest/tests/fixtures/notify-turn-complete-question.json`
- Create: `codex/work-digest/tests/fixtures/notify-turn-complete-progress.json`
- Create: `codex/work-digest/tests/test_notify.py`

**Step 1: Add notify payload fixtures**

Create fixture payloads that represent:
- approval requested event
- completed turn with a completion-style final message
- completed turn with a user-confirmation final message
- completed turn with progress-only message that should be ignored

**Step 2: Write failing tests against `notify.sh`**

Use `subprocess.run()` with:
- stdin from fixture JSON
- env `TELEGRAM_DRY_RUN=1`
- optional env `NOTIFY_NOW=1710000000` to stabilize dedupe timestamps

Coverage:

```python
def test_notify_sends_for_approval_requested(): ...
def test_notify_sends_for_completion_message(): ...
def test_notify_sends_for_question_message(): ...
def test_notify_skips_progress_only_message(): ...
def test_notify_dedupes_repeated_message(): ...
```

**Step 3: Run the tests to confirm RED**

Run:

```bash
python3 -m unittest discover -s codex/work-digest/tests -p 'test_notify.py' -v
```

Expected:
- FAIL because `notify.sh` does not exist yet

**Step 4: Commit**

```bash
git add codex/work-digest/tests/fixtures/notify-*.json codex/work-digest/tests/test_notify.py
git commit -m "test(codex-work-digest): add notify fixtures and failing tests"
```

---

### Task 5: Implement `notify.sh`

**Files:**
- Create: `codex/work-digest/scripts/notify.sh`
- Test: `codex/work-digest/tests/test_notify.py`

**Step 1: Implement entrypoint contract**

`notify.sh` should:
- read stdin JSON payload
- determine event type
- extract session/thread id and last agent message
- classify whether the message is:
  - completion
  - question/decision request
  - ignore

Use `python3 -c` helpers inside the script for JSON parsing instead of brittle grep-only parsing.

**Step 2: Add dry-run mode**

Support:
- `TELEGRAM_DRY_RUN=1` -> print computed notification text and exit 0
- `NOTIFY_NOW` override for deterministic tests

**Step 3: Add dedupe**

Use `codex/work-digest/state/notify_state.json` or `/tmp/codex-notify-dedup` with keys:
- session id
- event type
- message hash

Skip repeated notifications within 30 seconds.

**Step 4: Send Telegram only for allowed cases**

Rules:
- `approval-requested` -> always send
- `agent-turn-complete` -> only send on completion/question patterns
- no send for progress commentary

Message format example:

```text
[Codex] daye-agent-toolkit
작업 완료
<last_agent_message excerpt>
```

**Step 5: Run tests to confirm GREEN**

Run:

```bash
python3 -m unittest discover -s codex/work-digest/tests -p 'test_notify.py' -v
```

Expected:
- PASS

**Step 6: Smoke-test dry-run manually**

Run:

```bash
TELEGRAM_DRY_RUN=1 bash codex/work-digest/scripts/notify.sh < codex/work-digest/tests/fixtures/notify-turn-complete-finished.json
```

Expected:
- one completion notification text printed to stdout

**Step 7: Commit**

```bash
git add codex/work-digest/scripts/notify.sh
git commit -m "feat(codex-work-digest): add codex notify script"
```

---

### Task 6: Wrapper tests and implementation

**Files:**
- Create: `codex/work-digest/tests/fixtures/mock_codex.sh`
- Create: `codex/work-digest/tests/test_wrapper.py`
- Create: `codex/work-digest/scripts/codex-wrapper.sh`

**Step 1: Create a mock Codex binary**

`mock_codex.sh` should:
- create a temp session JSONL
- write `session_meta`
- optionally append `compacted` event
- sleep briefly
- exit with a caller-controlled code

This avoids invoking the real Codex binary in wrapper tests.

**Step 2: Write failing wrapper tests**

Coverage:

```python
def test_wrapper_forwards_args_to_real_binary(): ...
def test_wrapper_calls_session_logger_on_compaction(): ...
def test_wrapper_calls_session_logger_on_session_end(): ...
def test_wrapper_preserves_real_exit_code(): ...
```

Implementation hint:
- allow env override `CODEX_REAL_BIN` for tests
- allow env override `CODEX_LOGGER_BIN` pointing to a fake logger recorder script

**Step 3: Run the tests to confirm RED**

Run:

```bash
python3 -m unittest discover -s codex/work-digest/tests -p 'test_wrapper.py' -v
```

Expected:
- FAIL because `codex-wrapper.sh` does not exist yet

**Step 4: Implement `codex-wrapper.sh`**

Requirements:
- `REAL_CODEX_BIN="${CODEX_REAL_BIN:-/opt/homebrew/bin/codex}"`
- launch the real binary with `"$@"`
- identify the matching session file by newest `~/.codex/sessions/**.jsonl` plus `cwd`
- poll the session file during execution
- when `compacted` or `context_compacted` first appears, invoke:

```bash
python3 codex/work-digest/scripts/session_logger.py --event compaction --session-id ... --transcript-path ... --cwd ...
```

- on process exit, invoke the same logger with `--event session_end`
- return the real binary's exit code unchanged

**Step 5: Run tests to confirm GREEN**

Run:

```bash
python3 -m unittest discover -s codex/work-digest/tests -p 'test_wrapper.py' -v
```

Expected:
- PASS

**Step 6: Smoke-test real pass-through**

Run:

```bash
bash codex/work-digest/scripts/codex-wrapper.sh --version
```

Expected:
- same version output as `/opt/homebrew/bin/codex --version`

**Step 7: Commit**

```bash
git add codex/work-digest/tests/fixtures/mock_codex.sh codex/work-digest/tests/test_wrapper.py codex/work-digest/scripts/codex-wrapper.sh
git commit -m "feat(codex-work-digest): add codex wrapper lifecycle hook"
```

---

### Task 7: Wire local Codex and shell configuration

**Files:**
- Modify: `~/.codex/config.toml`
- Modify: `~/.zshrc`

**Step 1: Back up the current user files**

Run:

```bash
cp ~/.codex/config.toml ~/.codex/config.toml.bak-20260310
cp ~/.zshrc ~/.zshrc.bak-20260310
```

**Step 2: Wire `notify` into Codex config**

Update `~/.codex/config.toml`:

```toml
notify = ["bash", "/Users/dayejeong/git_workplace/daye-agent-toolkit/codex/work-digest/scripts/notify.sh"]

[tui]
notifications = ["approval-requested", "agent-turn-complete"]
```

Preserve existing `[tui]` keys such as `status_line`; only add `notifications`.

**Step 3: Route `codex` through the wrapper in zsh**

Add to `~/.zshrc`:

```bash
codex() {
  /Users/dayejeong/git_workplace/daye-agent-toolkit/codex/work-digest/scripts/codex-wrapper.sh "$@"
}
```

If an existing `codex` alias/function exists, replace it rather than duplicating it.

**Step 4: Reload shell config**

Run:

```bash
source ~/.zshrc
type codex
```

Expected:
- `codex is a shell function`

**Step 5: Verify notify wiring**

Run:

```bash
python3 - <<'PY'
import tomllib, pathlib
cfg = tomllib.loads(pathlib.Path.home().joinpath('.codex/config.toml').read_text())
print(cfg.get('notify'))
print(cfg.get('tui', {}).get('notifications'))
PY
```

Expected:
- notify path points to repo `notify.sh`
- notifications list contains `approval-requested` and `agent-turn-complete`

**Step 6: Commit repo-side changes only**

Do not commit dotfiles. Commit only repo files that document or support the wiring if needed.

---

### Task 8: End-to-end verification

**Files:**
- Verify only; no new files unless fixing defects discovered during verification

**Step 1: Run the full local test set**

Run:

```bash
python3 -m unittest discover -s codex/work-digest/tests -v
```

Expected:
- all tests PASS

**Step 2: Verify syntax for Python files**

Run:

```bash
python3 -m py_compile codex/work-digest/scripts/_common.py codex/work-digest/scripts/session_logger.py
```

Expected:
- no output

**Step 3: Verify notify dry-run**

Run:

```bash
TELEGRAM_DRY_RUN=1 bash codex/work-digest/scripts/notify.sh < codex/work-digest/tests/fixtures/notify-turn-complete-question.json
```

Expected:
- one question-style notification text is printed

**Step 4: Verify session logger against fixtures**

Run:

```bash
python3 codex/work-digest/scripts/session_logger.py --event compaction --transcript-path codex/work-digest/tests/fixtures/compaction.jsonl --session-id test-compaction --cwd /Users/dayejeong/git_workplace/daye-agent-toolkit
python3 codex/work-digest/scripts/session_logger.py --event session_end --transcript-path codex/work-digest/tests/fixtures/session_end.jsonl --session-id test-session-end --cwd /Users/dayejeong/git_workplace/daye-agent-toolkit
```

Expected:
- `codex/work-digest/work-log/<today>.md` gets two sections
- sections show `source: codex`
- one section shows `event: compaction`, one shows `event: session_end`

**Step 5: Verify wrapper pass-through**

Run:

```bash
bash codex/work-digest/scripts/codex-wrapper.sh --version
```

Expected:
- version command succeeds
- no recursive logger loop

**Step 6: Final commit(s)**

Commit implementation work in focused chunks. Avoid `git add .` and stage exact files only.

---

Plan complete and saved to `docs/plans/2026-03-10-codex-work-digest.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
