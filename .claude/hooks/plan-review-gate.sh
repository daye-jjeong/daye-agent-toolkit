#!/bin/bash
set -e

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE_PATH" == */docs/plans/*.md ]]; then
  FILENAME=$(basename "$FILE_PATH")

  jq -n \
    --arg filename "$FILENAME" \
    '{
      "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": "⚠ GATE 2 TRIGGERED: Plan file written (\($filename)). You MUST now execute the Plan Review Checklist before proceeding to execution:\n\n1. All file paths verified against actual codebase (3-Example Rule)\n2. Naming conventions match existing patterns\n3. Task dependencies are correct\n4. Edge cases from brainstorming are covered\n5. No tasks reference non-existent functions/modules\n6. Test strategy covers actual requirements, not just code presence\n\nDo NOT proceed to subagent-driven-development or executing-plans until this checklist is complete and shown to the user."
      }
    }'
fi

exit 0
