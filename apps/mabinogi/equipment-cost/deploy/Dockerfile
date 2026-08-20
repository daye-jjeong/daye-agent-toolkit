# 표준 라이브러리만 쓴다 — 설치할 게 없어서 이미지가 얇다.
FROM python:3.12-slim

WORKDIR /app
COPY scripts/ /app/scripts/

# 레시피·아이템이 든 씨앗. 먼저 만들어 둘 것:
#   python3 scripts/collect.py seed ~/.mabi-equipment-cost/data.db deploy/seed.db
# 상세 API는 IP 단위 쿼터가 걸려 새 환경에서 다시 받으려면 몇 시간이 든다.
# 시세는 쿼터가 없으므로 서버가 뜨고 3분 안에 스스로 채운다.
COPY deploy/seed.db /data/data.db

# 플랫폼이 $PORT를 주면 그걸 쓴다(Render·Fly 등). 없으면 8765.
ENV PORT=8765
EXPOSE 8765

# --public: 0.0.0.0 바인딩 + 새로고침 버튼 끔 + 3분마다 서버가 직접 수집.
# 버튼을 남기면 방문자마다 원본 API를 때려 서버 IP 하나로 요청이 몰린다.
CMD python3 scripts/serve.py ${PORT} /data/data.db --public
