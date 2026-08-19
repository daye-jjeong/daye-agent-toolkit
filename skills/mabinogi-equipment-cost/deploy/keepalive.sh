#!/bin/bash
# serve.py가 죽으면 되살린다. cloudflared는 건드리지 않는다 —
# 터널은 localhost:8765를 보므로 서버만 다시 뜨면 같은 주소로 이어진다.
# (cloudflared를 재시작하면 주소가 바뀐다. 그래서 여기서 손대지 않는다.)

APP="$1"          # 스킬 디렉토리 (serve.py가 있는 곳의 상위)
LOG="$2"

# 파이썬을 절대경로로 박는다. macOS 기본 /usr/bin/python3(3.9)은 2018년
# LibreSSL을 써서, 원본 앞단 Cloudflare가 그 TLS 인사 모양을 보고 봇으로
# 판정해 403으로 막는다 (2026-08-19 16:17부터 실측). OpenSSL 3.x를 쓰는
# 파이썬이면 통과한다. PATH에 기대면 어느 셸에서 띄웠느냐로 갈린다.
PY="${MABI_PYTHON:-/opt/homebrew/bin/python3}"
[ -x "$PY" ] || PY="$(command -v python3)"

cd "$APP" || exit 1
while true; do
  if ! pgrep -f "serve.py 8765 --public" > /dev/null; then
    echo "[$(date '+%H:%M:%S')] serve.py가 없다 — 다시 띄운다" >> "$LOG"
    nohup "$PY" scripts/serve.py 8765 --public >> "$LOG" 2>&1 &
  fi
  sleep 20
done
