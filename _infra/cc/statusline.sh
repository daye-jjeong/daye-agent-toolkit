#!/bin/bash
# Claude Code 커스텀 상태줄
# 표시: 모델 | git branch | 컨텍스트 사용률 | 변경 라인 | 세션 시간 | 비용

input=$(cat)

model=$(echo "$input" | jq -r '.model.display_name // .model.id // "unknown"')
cwd=$(echo "$input" | jq -r '.cwd // "."')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
total=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')
lines_add=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
lines_del=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
duration_ms=$(echo "$input" | jq -r '.cost.total_duration_ms // empty')

# ANSI colors
PURPLE=$'\033[35m'
CYAN=$'\033[36m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
BLUE=$'\033[34m'
GRAY=$'\033[90m'
RESET=$'\033[0m'

# Git branch
branch=$(git -C "$cwd" branch --show-current 2>/dev/null)

format_tokens() {
  local n=$1
  if [ -n "$n" ] && [ "$n" != "null" ]; then
    awk "BEGIN { printf \"%.0fk\", $n/1000 }"
  fi
}

format_duration() {
  local ms=$1
  local total_sec=$((ms / 1000))
  local hours=$((total_sec / 3600))
  local mins=$(( (total_sec % 3600) / 60 ))
  if [ "$hours" -gt 0 ]; then
    printf "%dh%dm" "$hours" "$mins"
  else
    printf "%dm" "$mins"
  fi
}

# 1. Model (purple)
out="${PURPLE}${model}${RESET}"

# 2. Git branch (cyan)
if [ -n "$branch" ]; then
  out="${out} ${CYAN} ${branch}${RESET}"
fi

# 3. Context usage (green / yellow / red)
if [ -n "$used_pct" ] && [ "$used_pct" != "null" ]; then
  total_k=$(format_tokens "$total")
  used_tokens=$(awk "BEGIN { printf \"%.0f\", $total * $used_pct / 100 }")
  used_k=$(format_tokens "$used_tokens")

  if [ "$used_pct" -ge 80 ] 2>/dev/null; then
    ctx_color="$RED"
  elif [ "$used_pct" -ge 60 ] 2>/dev/null; then
    ctx_color="$YELLOW"
  else
    ctx_color="$GREEN"
  fi

  out="${out} ${ctx_color}${used_pct}% ${used_k}/${total_k}${RESET}"
fi

# 4. Lines changed (blue)
if [ "$lines_add" != "0" ] || [ "$lines_del" != "0" ]; then
  out="${out} ${BLUE}+${lines_add} -${lines_del}${RESET}"
fi

# 5. Session duration (gray)
if [ -n "$duration_ms" ] && [ "$duration_ms" != "null" ] && [ "$duration_ms" -gt 0 ] 2>/dev/null; then
  dur=$(format_duration "$duration_ms")
  out="${out} ${GRAY}${dur}${RESET}"
fi

# 6. Cost (gray)
if [ -n "$cost" ] && [ "$cost" != "null" ]; then
  cost_fmt=$(awk "BEGIN { printf \"%.2f\", $cost }")
  out="${out} ${GRAY}\$${cost_fmt}${RESET}"
fi

printf "%s" "$out"
