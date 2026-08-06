#!/usr/bin/env python3
"""Context usage monitor — UserPromptSubmit hook.

매 사용자 입력 직전에 transcript JSONL을 파싱하여 누적 토큰을 계산하고,
50%/70%/85% 임계값 도달 시 Claude 컨텍스트에 압축 권장 신호를 주입한다.

컨텍스트 상한은 transcript에 기록된 모델명으로 MODEL_LIMITS에서 찾는다.
모르는 모델이면 DEFAULT_MAX. CLAUDE_HOOK_CTX_MAX env 를 주면 그게 최우선.
"""

import json
import os
import sys
from pathlib import Path

# 모델별 컨텍스트 상한. 새 모델이 나오면 여기만 고친다.
MODEL_LIMITS = {
    "claude-opus-5": 1_000_000,
}
DEFAULT_MAX = 1_000_000

THRESHOLDS = [
    (
        0.85,
        "🚨 컨텍스트 {pct}% ({used}/{maxk}, {model}) — 즉시 /compact 또는 세션 분할 필요. auto-compaction 신뢰 불가.",
    ),
    (
        0.70,
        "⚠️ 컨텍스트 {pct}% ({used}/{maxk}, {model}) — 다음 마일스톤 종료 시 /compact 강력 권장.",
    ),
    (
        0.50,
        "💡 컨텍스트 {pct}% ({used}/{maxk}, {model}) — 곧 압축 타이밍. 마일스톤 전환 시점이면 /compact 제안.",
    ),
]


def resolve_max(model: str) -> int:
    """상한 결정 우선순위: env > 모델별 테이블 > 기본값."""
    override = os.environ.get("CLAUDE_HOOK_CTX_MAX")
    if override:
        try:
            return int(override)
        except ValueError:
            pass
    return MODEL_LIMITS.get(model, DEFAULT_MAX)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    transcript_path = data.get("transcript_path")
    if not transcript_path:
        sys.exit(0)
    transcript = Path(transcript_path)
    if not transcript.exists():
        sys.exit(0)

    last_usage = None
    last_model = ""
    try:
        with transcript.open() as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = entry.get("message") if isinstance(entry, dict) else None
                if not isinstance(msg, dict):
                    continue
                if isinstance(msg.get("usage"), dict):
                    last_usage = msg["usage"]
                if isinstance(msg.get("model"), str):
                    last_model = msg["model"]
    except OSError:
        sys.exit(0)

    if not last_usage:
        sys.exit(0)

    max_tokens = resolve_max(last_model)
    if max_tokens <= 0:
        sys.exit(0)

    total = (
        last_usage.get("input_tokens", 0)
        + last_usage.get("cache_creation_input_tokens", 0)
        + last_usage.get("cache_read_input_tokens", 0)
    )
    ratio = total / max_tokens

    # 모르는 모델이면 표시에 물음표를 붙여, 잘못된 상한으로 재고 있음을 드러낸다.
    model_label = last_model.replace("claude-", "") or "unknown"
    if last_model not in MODEL_LIMITS:
        model_label += "?"

    for threshold, template in THRESHOLDS:
        if ratio >= threshold:
            msg_text = template.format(
                pct=int(ratio * 100),
                used=f"{total // 1000}k",
                maxk=f"{max_tokens // 1000}k",
                model=model_label,
            )
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "UserPromptSubmit",
                            "additionalContext": msg_text,
                        }
                    }
                )
            )
            break

    sys.exit(0)


if __name__ == "__main__":
    main()
