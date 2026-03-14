#!/bin/bash
# Claude Code 커스텀 상태줄 (2-line, session-colored)
# L1(세션 컬러): 모델 · 프로젝트 · worktree · git(+상세) · 계정
# L2(검정 배경): 시간 · 컨텍스트 · 비용 · 캐시 · 속도 · 변경라인 · quota · API효율

input=$(cat)
COLS=$(tput cols 2>/dev/null || echo 120)

# ── Extract all fields (single jq) ────────────────────────
IFS=$'\t' read -r model cwd project_dir used_pct total cost duration_ms \
  lines_add lines_del total_in total_out output_style \
  cache_read cache_create input_tokens wt_name session_id < <(
  echo "$input" | jq -r '[
    (.model.display_name // .model.id // "unknown"),
    (.workspace.current_dir // .cwd // "."),
    (.workspace.project_dir // ""),
    (.context_window.used_percentage // ""),
    (.context_window.context_window_size // ""),
    (.cost.total_cost_usd // ""),
    (.cost.total_duration_ms // ""),
    (.cost.total_lines_added // 0),
    (.cost.total_lines_removed // 0),
    (.context_window.total_input_tokens // 0),
    (.context_window.total_output_tokens // 0),
    (.output_style.name // ""),
    (.context_window.current_usage.cache_read_input_tokens // 0),
    (.context_window.current_usage.cache_creation_input_tokens // 0),
    (.context_window.current_usage.input_tokens // 0),
    (.worktree.name // ""),
    (.session_id // "")
  ] | @tsv'
)

# ── Session color (hash session_id → 12 hues) ─────────────
PHASH=$(printf '%s' "${session_id:-$cwd}" | cksum | cut -d' ' -f1)
COLOR_IDX=$((PHASH % 12))

case $COLOR_IDX in
  0)  BG_R=105; BG_G=145; BG_B=225 ;; # blue
  1)  BG_R=130; BG_G=190; BG_B=130 ;; # green
  2)  BG_R=190; BG_G=130; BG_B=175 ;; # pink
  3)  BG_R=200; BG_G=170; BG_B=100 ;; # amber
  4)  BG_R=100; BG_G=185; BG_B=185 ;; # teal
  5)  BG_R=175; BG_G=130; BG_B=190 ;; # purple
  6)  BG_R=110; BG_G=170; BG_B=210 ;; # sky
  7)  BG_R=180; BG_G=190; BG_B=110 ;; # olive
  8)  BG_R=200; BG_G=140; BG_B=130 ;; # coral
  9)  BG_R=130; BG_G=170; BG_B=180 ;; # steel
  10) BG_R=190; BG_G=175; BG_B=120 ;; # khaki
  11) BG_R=160; BG_G=130; BG_B=190 ;; # violet
esac

RST="\033[0m"
BG1="\033[48;2;${BG_R};${BG_G};${BG_B}m"
TXT_R=$((BG_R * 15 / 100)); TXT_G=$((BG_G * 15 / 100)); TXT_B=$((BG_B * 15 / 100))
SEP_R=$((BG_R * 40 / 100)); SEP_G=$((BG_G * 40 / 100)); SEP_B=$((BG_B * 40 / 100))
L1_TXT="\033[38;2;${TXT_R};${TXT_G};${TXT_B}m"
L1_BOLD="\033[38;2;${TXT_R};${TXT_G};${TXT_B};1m"
L1_SEP="\033[38;2;${SEP_R};${SEP_G};${SEP_B}m│"
B1="${RST}${BG1}"

# Line 2: no background (terminal default)
B2="${RST}"
L2_TXT="\033[38;2;100;100;100m"
L2_DIM="\033[38;2;150;150;150m"
L2_SEP="${L2_DIM}│"

# ── Helpers ────────────────────────────────────────────────
format_k() {
  local n=$1
  [ -n "$n" ] && [ "$n" != "null" ] && [ "$n" != "0" ] || { echo "0"; return; }
  awk "BEGIN { v=$n/1000; if (v >= 100) printf \"%.0fK\", v; else printf \"%.1fK\", v }"
}

format_duration() {
  local ms=$1
  [ -z "$ms" ] || [ "$ms" = "null" ] || [ "$ms" -le 0 ] 2>/dev/null && return
  local s=$((ms / 1000)) h=$((s / 3600)) m=$(((s % 3600) / 60))
  [ "$h" -gt 0 ] && printf "%dh%dm" "$h" "$m" || printf "%dm" "$m"
}

format_remaining() {
  local reset_ts=$1
  [ -z "$reset_ts" ] || [ "$reset_ts" = "null" ] && return
  local now=$(date +%s)
  local epoch=$(date -jf "%Y-%m-%dT%H:%M:%S" "$(echo "$reset_ts" | cut -d. -f1 | sed 's/+.*//')" +%s 2>/dev/null)
  [ -z "$epoch" ] && return
  local diff=$((epoch - now))
  [ "$diff" -le 0 ] && { echo "곧"; return; }
  local h=$((diff / 3600)) m=$(((diff % 3600) / 60))
  if [ "$h" -gt 24 ]; then printf "%dd%dh" $((h / 24)) $((h % 24))
  elif [ "$h" -gt 0 ]; then printf "%dh%dm" "$h" "$m"
  else printf "%dm" "$m"
  fi
}

pct_color() {
  local p=$1
  if [ "$p" -gt 80 ] 2>/dev/null; then printf "\033[38;2;180;50;50m"
  elif [ "$p" -gt 50 ] 2>/dev/null; then printf "\033[38;2;160;120;20m"
  else printf "\033[38;2;30;130;50m"
  fi
}

# ── Git info (cached 5s) ──────────────────────────────────
GIT_CACHE="/tmp/statusline-git-$(printf '%s' "$cwd" | md5 -q 2>/dev/null || printf '%s' "$cwd" | md5sum 2>/dev/null | cut -d' ' -f1)"

git_cache_stale() {
  [ ! -f "$GIT_CACHE" ] || \
  [ $(($(date +%s) - $(stat -f %m "$GIT_CACHE" 2>/dev/null || echo 0))) -gt 5 ]
}

branch="" short_hash="" git_staged=0 git_modified=0 git_untracked=0
if git_cache_stale; then
  if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
    short_hash=$(git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
    git_staged=$(git -C "$cwd" diff --cached --numstat 2>/dev/null | wc -l | tr -d " ")
    git_modified=$(git -C "$cwd" diff --numstat 2>/dev/null | wc -l | tr -d " ")
    git_untracked=$(git -C "$cwd" ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d " ")
    printf '%s\n' "${branch}|${short_hash}|${git_staged}|${git_modified}|${git_untracked}" > "$GIT_CACHE"
  else
    printf '%s\n' "||||" > "$GIT_CACHE"
  fi
fi
IFS='|' read -r branch short_hash git_staged git_modified git_untracked < "$GIT_CACHE"

# ── Quota (cached 5min) ───────────────────────────────────
QUOTA_CACHE="/tmp/statusline-quota.json"
QUOTA_ACCT_CACHE="/tmp/statusline-acct"
QUOTA_MAX_AGE=300

quota_cache_stale() {
  [ ! -f "$QUOTA_CACHE" ] || \
  [ $(($(date +%s) - $(stat -f %m "$QUOTA_CACHE" 2>/dev/null || echo 0))) -gt $QUOTA_MAX_AGE ]
}

acct_name="" sub_type=""
if quota_cache_stale; then
  for acct_try in "$(whoami)" "Claude Code"; do
    CREDS=$(security find-generic-password -s "Claude Code-credentials" -a "$acct_try" -w 2>/dev/null) || continue
    TOKEN=$(echo "$CREDS" | jq -r '.claudeAiOauth.accessToken // empty')
    [ -z "$TOKEN" ] && continue
    acct_name="$acct_try"
    RESULT=$(curl -s --max-time 3 "https://api.anthropic.com/api/oauth/usage" \
      -H "Authorization: Bearer $TOKEN" \
      -H "anthropic-beta: oauth-2025-04-20" \
      -H "Content-Type: application/json" 2>/dev/null)
    if echo "$RESULT" | jq -e '.five_hour' > /dev/null 2>&1; then
      echo "$RESULT" > "$QUOTA_CACHE"
      SUB_TYPE=$(echo "$CREDS" | jq -r '.claudeAiOauth.subscriptionType // empty')
      printf '%s\n%s' "$acct_name" "$SUB_TYPE" > "$QUOTA_ACCT_CACHE"
      break
    fi
  done
fi

# Read cached quota (single jq)
five_hr="" five_hr_reset="" seven_day="" seven_day_reset="" seven_day_s="" seven_day_s_reset=""
if [ -f "$QUOTA_CACHE" ]; then
  IFS=$'\t' read -r five_hr five_hr_reset seven_day seven_day_reset seven_day_s seven_day_s_reset < <(
    jq -r '[
      (.five_hour.utilization // ""),
      (.five_hour.resets_at // ""),
      (.seven_day.utilization // ""),
      (.seven_day.resets_at // ""),
      (.seven_day_sonnet.utilization // ""),
      (.seven_day_sonnet.resets_at // "")
    ] | @tsv' "$QUOTA_CACHE" 2>/dev/null
  )
fi

[ -f "$QUOTA_ACCT_CACHE" ] && { acct_name=$(sed -n '1p' "$QUOTA_ACCT_CACHE"); sub_type=$(sed -n '2p' "$QUOTA_ACCT_CACHE"); }

# ── Computed values ────────────────────────────────────────
pct_int=0
[ -n "$used_pct" ] && [ "$used_pct" != "null" ] && pct_int=$(printf "%.0f" "$used_pct" 2>/dev/null || echo 0)

BAR_W=10
FILLED=$((pct_int * BAR_W / 100))
[ "$FILLED" -gt "$BAR_W" ] && FILLED=$BAR_W
EMPTY=$((BAR_W - FILLED))
CTX_CLR=$(pct_color "$pct_int")
BAR=""
[ "$FILLED" -gt 0 ] && BAR=$(printf "%${FILLED}s" | tr ' ' '▓')
[ "$EMPTY" -gt 0 ] && BAR="${BAR}$(printf "%${EMPTY}s" | tr ' ' '░')"

used_k="" total_k=""
if [ -n "$total" ] && [ "$total" != "null" ] && [ -n "$used_pct" ] && [ "$used_pct" != "null" ]; then
  used_tokens=$(awk "BEGIN { printf \"%.0f\", $total * $used_pct / 100 }")
  used_k=$(format_k "$used_tokens")
  total_k=$(format_k "$total")
fi

cache_hit_pct=""
total_cache=$((cache_read + cache_create + input_tokens))
[ "$total_cache" -gt 0 ] 2>/dev/null && cache_hit_pct=$((cache_read * 100 / total_cache))

token_speed=""
if [ -n "$duration_ms" ] && [ "$duration_ms" != "null" ] && [ "$duration_ms" -gt 0 ] 2>/dev/null; then
  total_tokens=$((total_in + total_out))
  [ "$total_tokens" -gt 0 ] && token_speed=$(awk "BEGIN { v=$total_tokens / ($duration_ms / 60000); if (v >= 1000) printf \"%.1fK\", v/1000; else printf \"%.0f\", v }")
fi

dir_name="${cwd##*/}"
[ -n "$project_dir" ] && [ "$project_dir" != "null" ] && dir_name="${project_dir##*/}"

dur=$(format_duration "$duration_ms")
dur_clr="${L2_TXT}"
if [ -n "$duration_ms" ] && [ "$duration_ms" != "null" ] && [ "$duration_ms" -gt 0 ] 2>/dev/null; then
  h=$((duration_ms / 1000 / 3600))
  if [ "$h" -ge 3 ]; then dur_clr="\033[38;2;180;50;50m"
  elif [ "$h" -ge 1 ]; then dur_clr="\033[38;2;160;120;20m"
  else dur_clr="\033[38;2;30;130;50m"
  fi
fi

# ── LINE 1 (session-colored): model · project · worktree · git · account ─
line1="${B1} ${L1_BOLD}${model}${B1}"

[ -n "$output_style" ] && [ "$output_style" != "null" ] && [ "$output_style" != "default" ] && \
  line1+="${L1_TXT}(${output_style})${B1}"

line1+=" ${L1_SEP}${B1} ${L1_TXT}${dir_name}${B1}"

# worktree: UUID 패턴(세션 ID 누출)이면 숨김
if [ -n "$wt_name" ] && [ "$wt_name" != "null" ] && \
   ! [[ "$wt_name" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
  line1+=" ${L1_SEP}${B1} ${L1_BOLD}⎇ ${wt_name}${B1}"
fi

if [ -n "$branch" ]; then
  line1+=" ${L1_SEP}${B1} ${L1_TXT}${branch}${B1}"
  [ -n "$short_hash" ] && line1+="${L1_TXT}@${short_hash}${B1}"
  git_info=""
  [ "$git_staged" -gt 0 ] 2>/dev/null && git_info="+${git_staged}"
  [ "$git_modified" -gt 0 ] 2>/dev/null && git_info="${git_info:+$git_info }!${git_modified}"
  [ "$git_untracked" -gt 0 ] 2>/dev/null && git_info="${git_info:+$git_info }?${git_untracked}"
  [ -n "$git_info" ] && line1+=" ${L1_BOLD}${git_info}${B1}"
fi

if [ -n "$acct_name" ]; then
  sub_label=""
  [ -n "$sub_type" ] && sub_label="(${sub_type})"
  line1+=" ${L1_SEP}${B1} ${L1_TXT}${acct_name}${sub_label}${B1}"
fi

line1+=" "

# ── LINE 2: metrics (separator before each item except first) ─
line2="${B2} "
l2_sep=""

if [ -n "$dur" ]; then
  line2+="${L2_TXT}⏱ ${dur_clr}${dur}${B2}"
  l2_sep=" ${L2_SEP}${B2} "
fi

if [ -n "$used_pct" ] && [ "$used_pct" != "null" ]; then
  line2+="${l2_sep}${CTX_CLR}${BAR} ${pct_int}%${B2}"
  [ -n "$used_k" ] && line2+=" ${L2_DIM}${used_k}/${total_k}${B2}"
  l2_sep=" ${L2_SEP}${B2} "
fi

if [ -n "$cost" ] && [ "$cost" != "null" ]; then
  cost_fmt=$(awk "BEGIN { printf \"%.2f\", $cost }")
  line2+="${l2_sep}\033[38;2;160;120;20m\$${cost_fmt}${B2}"
  l2_sep=" ${L2_SEP}${B2} "
fi

if [ -n "$cache_hit_pct" ]; then
  if [ "$cache_hit_pct" -ge 70 ]; then ch_clr="\033[38;2;30;130;50m"
  elif [ "$cache_hit_pct" -ge 40 ]; then ch_clr="\033[38;2;160;120;20m"
  else ch_clr="\033[38;2;180;50;50m"
  fi
  line2+="${l2_sep}${ch_clr}⚡${cache_hit_pct}%${B2}"
  l2_sep=" ${L2_SEP}${B2} "
fi

if [ -n "$token_speed" ]; then
  line2+="${l2_sep}\033[38;2;40;90;160m${token_speed}/m${B2}"
  l2_sep=" ${L2_SEP}${B2} "
fi

if [ "$lines_add" != "0" ] || [ "$lines_del" != "0" ]; then
  line2+="${l2_sep}\033[38;2;30;130;50m+${lines_add}${B2} \033[38;2;180;50;50m-${lines_del}${B2}"
fi

# ── LINE 3: quota ──────────────────────────────────────────
line3=""

if [ -n "$five_hr" ] && [ "$five_hr" != "null" ]; then
  five_int=$(printf "%.0f" "$five_hr")
  five_remain=$(format_remaining "$five_hr_reset")
  qc=$(pct_color "$five_int")
  line3+="${L2_TXT}5h ${qc}${five_int}%${B2}"
  [ -n "$five_remain" ] && line3+=" ${L2_DIM}${five_remain}${B2}"
fi

if [ -n "$seven_day" ] && [ "$seven_day" != "null" ]; then
  seven_int=$(printf "%.0f" "$seven_day")
  seven_remain=$(format_remaining "$seven_day_reset")
  qc=$(pct_color "$seven_int")
  [ -n "$line3" ] && line3+=" ${L2_SEP}${B2} "
  line3+="${L2_TXT}7d ${qc}${seven_int}%${B2}"
  [ -n "$seven_remain" ] && line3+=" ${L2_DIM}${seven_remain}${B2}"
fi

if [ -n "$seven_day_s" ] && [ "$seven_day_s" != "null" ]; then
  seven_s_int=$(printf "%.0f" "$seven_day_s")
  seven_s_remain=$(format_remaining "$seven_day_s_reset")
  qc=$(pct_color "$seven_s_int")
  [ -n "$line3" ] && line3+=" ${L2_SEP}${B2} "
  line3+="${L2_TXT}7dS ${qc}${seven_s_int}%${B2}"
  [ -n "$seven_s_remain" ] && line3+=" ${L2_DIM}${seven_s_remain}${B2}"
fi

# ── Tab title ─────────────────────────────────────────────
_TAB="${dir_name}"
[ -n "$wt_name" ] && [ "$wt_name" != "null" ] && _TAB="${dir_name}:${wt_name}"
printf '\033]1;%s\007' "$_TAB" > /dev/tty 2>/dev/null || true

# ── Output (overflow-safe) ────────────────────────────────
echo -e "\033[?7l${line1}${BG1}\033[K${RST}"
echo -e "${line2}\033[K${RST}"
[ -n "$line3" ] && echo -e "${line3}\033[K${RST}\033[?7h" || printf '\033[?7h'
