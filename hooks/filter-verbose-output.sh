#!/bin/bash
# PostToolUse hook: filters verbose test/build output before it enters context.
# Targets: jest, vitest, pytest, tsc, npm run build, npx nest build
# Keeps only failures/errors + truncates to 150 lines max.

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name // empty')

# Only process Bash tool results
if [[ "$tool_name" != "Bash" ]]; then
  echo '{}'
  exit 0
fi

stdout=$(echo "$input" | jq -r '.tool_result.stdout // empty')
stderr=$(echo "$input" | jq -r '.tool_result.stderr // empty')
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# Detect test runners and build tools
is_test=false
is_build=false

if [[ "$command" =~ (jest|vitest|pytest|go\ test|npm\ test|npx\ jest|yarn\ test) ]]; then
  is_test=true
fi

if [[ "$command" =~ (tsc|npm\ run\ build|npx\ nest\ build|yarn\ build) ]]; then
  is_build=true
fi

# Skip if not a recognized command
if ! $is_test && ! $is_build; then
  echo '{}'
  exit 0
fi

# Check exit code - if success with no errors, return minimal summary
exit_code=$(echo "$input" | jq -r '.tool_result.exitCode // "0"')

if [[ "$is_test" == true ]]; then
  if [[ "$exit_code" == "0" ]]; then
    # Tests passed - extract summary line only
    summary=$(echo "$stdout" | grep -E "(Tests?:.*passed|passed|PASS|test suites?)" | tail -5)
    if [[ -z "$summary" ]]; then
      summary="All tests passed."
    fi
    jq -n --arg s "$summary" '{
      "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "suppressOutput": true,
        "message": $s
      }
    }'
  else
    # Tests failed - keep only failure context
    filtered=$(echo "$stdout$stderr" | grep -B 2 -A 10 -E "(FAIL|FAILED|ERROR|error:|Error:|✕|✗|AssertionError|Expected|Received|not\.to)" | head -150)
    if [[ -z "$filtered" ]]; then
      filtered=$(echo "$stdout$stderr" | tail -80)
    fi
    jq -n --arg s "$filtered" '{
      "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "suppressOutput": true,
        "message": $s
      }
    }'
  fi
elif [[ "$is_build" == true ]]; then
  if [[ "$exit_code" == "0" ]]; then
    summary="Build succeeded."
    # Still show warnings if any
    warnings=$(echo "$stdout$stderr" | grep -i "warning" | head -20)
    if [[ -n "$warnings" ]]; then
      summary="Build succeeded with warnings:\n$warnings"
    fi
    jq -n --arg s "$summary" '{
      "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "suppressOutput": true,
        "message": $s
      }
    }'
  else
    # Build failed - keep errors and nearby context
    filtered=$(echo "$stdout$stderr" | grep -B 2 -A 5 -E "(error TS|ERROR|error:|Error:|failed)" | head -150)
    if [[ -z "$filtered" ]]; then
      filtered=$(echo "$stdout$stderr" | tail -80)
    fi
    jq -n --arg s "$filtered" '{
      "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "suppressOutput": true,
        "message": $s
      }
    }'
  fi
fi
