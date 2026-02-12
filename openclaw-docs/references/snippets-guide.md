# Golden Snippets 관리 가이드

Golden Snippet은 자주 묻는 질문에 대한 사전 캐시된 답변.
스니펫으로 80-90%의 질문을 300-500 토큰으로 해결.

## 스니펫 위치

```
~/openclaw/data/docs-snippets/
├── telegram-setup.md
├── oauth-troubleshoot.md
├── skill-setup.md
├── cron-setup.md
├── config-basics.md
├── update-procedure.md
├── memory-search.md
└── multi-agent.md
```

## 스니펫 포맷

```markdown
---
topic: telegram-setup
source: https://docs.openclaw.ai/channels/telegram
expires: 2026-02-18
keywords: telegram, 텔레그램, 봇, 설정, token
---

# Telegram 설정

1. BotFather에서 봇 생성 → 토큰 받기
2. `openclaw configure` → telegram 섹션에 토큰 입력
3. `openclaw channels add telegram` 실행
4. 봇에게 `/start` 메시지 전송

## allowFrom 설정
...
```

## 새 스니펫 생성 기준

스니펫을 만들어야 하는 경우:
- 같은 질문이 **3회 이상** 반복될 때
- 답이 **500토큰 이내**로 정리 가능할 때
- 원본 문서가 **자주 바뀌지 않을 때** (TTL 7일+)

## 스니펫 갱신

1. `expires` 날짜 확인
2. 만료되었으면 원본 페이지 fetch:
   ```javascript
   web_fetch({ url: "<source-url>", extractMode: "markdown" })
   ```
3. 스니펫 내용 업데이트 + `expires` 갱신

## 인덱스 파일 (docs-index.json)

```json
{
  "pages": [
    {
      "path": "channels/telegram",
      "ttl_days": 7,
      "keywords": ["telegram", "tg", "텔레그램", "봇"]
    }
  ],
  "synonyms": {
    "telegram": ["tg", "텔레그램"],
    "configuration": ["config", "설정", "세팅"],
    "update": ["업데이트", "갱신"],
    "memory": ["메모리", "기억", "벡터"]
  }
}
```

한국어/영어 동의어를 포함하여 검색 정확도 향상.
