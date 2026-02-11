# OpenClaw Docs 전체 페이지 인덱스

Base URL: `https://docs.openclaw.ai`

## Getting Started
- `start/getting-started` — 설치 및 초기 설정
- `start/wizard` — 온보딩 마법사 (`openclaw onboard`)
- `start/setup` — 초기 셋업
- `start/onboarding` — 온보딩 가이드
- `start/hubs` — 유스케이스별 허브
- `start/bootstrapping` — 부트스트래핑
- `start/docs-directory` — 문서 디렉토리
- `start/showcase` — 쇼케이스
- `start/lore` — 프로젝트 히스토리

## Automation
- `automation/cron-jobs` — 크론 작업
- `automation/webhook` — 웹훅
- `automation/hooks` — 훅
- `automation/poll` — 폴링
- `automation/auth-monitoring` — 인증 모니터링
- `automation/cron-vs-heartbeat` — 크론 vs 하트비트
- `automation/gmail-pubsub` — Gmail PubSub
- `automation/troubleshooting` — 자동화 트러블슈팅

## Channels (20+)
- `channels/telegram` — Telegram
- `channels/discord` — Discord
- `channels/slack` — Slack
- `channels/whatsapp` — WhatsApp
- `channels/imessage` — iMessage
- `channels/msteams` — MS Teams
- `channels/signal` — Signal
- `channels/line` — LINE
- `channels/matrix` — Matrix
- `channels/mattermost` — Mattermost
- `channels/googlechat` — Google Chat
- `channels/irc` — IRC
- `channels/feishu` — Feishu
- `channels/zalo` / `channels/zalouser` — Zalo
- `channels/grammy` — Grammy (Telegram 프레임워크)
- `channels/groups` / `channels/group-messages` — 그룹 메시지
- `channels/broadcast-groups` — 브로드캐스트
- `channels/channel-routing` — 채널 라우팅
- `channels/pairing` — 채널 페어링
- `channels/location` — 위치 기반
- `channels/troubleshooting` — 채널 트러블슈팅

## CLI Commands (40+)
- `cli/agent` / `cli/agents` — 에이전트 관리
- `cli/channels` — 채널 관리
- `cli/configure` — 설정
- `cli/cron` — 크론 관리
- `cli/dashboard` — 대시보드
- `cli/gateway` — 게이트웨이
- `cli/health` — 상태 체크
- `cli/hooks` — 훅
- `cli/logs` — 로그
- `cli/memory` — 메모리
- `cli/message` — 메시지 전송
- `cli/models` — 모델 관리
- `cli/nodes` — 노드 관리
- `cli/onboard` — 온보딩
- `cli/plugins` — 플러그인
- `cli/sessions` — 세션
- `cli/skills` — 스킬
- `cli/status` — 상태
- `cli/security` — 보안
- `cli/sandbox` — 샌드박스
- `cli/browser` — 브라우저
- `cli/tui` — TUI
- `cli/update` — 업데이트
- `cli/setup` / `cli/reset` / `cli/uninstall` — 설치/초기화
- `cli/doctor` — 진단
- `cli/dns` / `cli/directory` — DNS/디렉토리
- `cli/voicecall` — 음성통화
- `cli/docs` — 문서
- `cli/pairing` — 페어링
- `cli/approvals` — 승인

## Concepts
- `concepts/agent` — 에이전트 런타임
- `concepts/agent-loop` — 에이전트 루프
- `concepts/agent-workspace` — 에이전트 워크스페이스
- `concepts/architecture` — 아키텍처
- `concepts/memory` — 메모리 시스템
- `concepts/session` / `concepts/sessions` — 세션
- `concepts/session-tool` — 세션 도구
- `concepts/session-pruning` — 세션 정리
- `concepts/multi-agent` — 멀티 에이전트
- `concepts/oauth` — OAuth
- `concepts/streaming` — 스트리밍
- `concepts/model-failover` — 모델 페일오버
- `concepts/model-providers` / `concepts/models` — 모델
- `concepts/system-prompt` — 시스템 프롬프트
- `concepts/context` — 컨텍스트
- `concepts/compaction` — 컴팩션
- `concepts/messages` — 메시지
- `concepts/queue` — 큐
- `concepts/retry` — 재시도
- `concepts/presence` — 프레즌스
- `concepts/timezone` — 타임존
- `concepts/typebox` — TypeBox
- `concepts/typing-indicators` — 타이핑 인디케이터
- `concepts/usage-tracking` — 사용량 추적
- `concepts/markdown-formatting` — 마크다운 포맷
- `concepts/features` — 전체 기능 목록

## Gateway
- `gateway/configuration` — 설정
- `gateway/configuration-examples` — 설정 예시
- `gateway/security` — 보안
- `gateway/sandboxing` — 샌드박싱
- `gateway/sandbox-vs-tool-policy-vs-elevated` — 샌드박스 비교
- `gateway/remote` — 원격 접속
- `gateway/tailscale` — Tailscale
- `gateway/troubleshooting` — 트러블슈팅
- `gateway/authentication` — 인증
- `gateway/protocol` — 프로토콜
- `gateway/bridge-protocol` — 브릿지 프로토콜
- `gateway/network-model` — 네트워크 모델
- `gateway/heartbeat` — 하트비트
- `gateway/health` — 헬스체크
- `gateway/doctor` — 닥터
- `gateway/logging` — 로깅
- `gateway/background-process` — 백그라운드 프로세스
- `gateway/local-models` — 로컬 모델
- `gateway/multiple-gateways` — 다중 게이트웨이
- `gateway/openai-http-api` — OpenAI HTTP API
- `gateway/tools-invoke-http-api` — 도구 HTTP API
- `gateway/cli-backends` — CLI 백엔드
- `gateway/bonjour` — Bonjour
- `gateway/discovery` — 디스커버리
- `gateway/gateway-lock` — 게이트웨이 락
- `gateway/pairing` — 페어링

## Install
- `install/installer` — 인스톨러
- `install/docker` — Docker
- `install/nix` — Nix
- `install/bun` — Bun
- `install/node` — Node.js
- `install/updating` — 업데이트
- `install/migrating` — 마이그레이션
- `install/uninstall` — 제거
- Cloud: `install/fly`, `install/gcp`, `install/hetzner`, `install/railway`, `install/render`, `install/northflank`, `install/ansible`
- `install/macos-vm` — macOS VM
- `install/development-channels` — 개발 채널
- `install/exe-dev` — 실행파일 개발

## Tools
- `tools/skills` — 스킬
- `tools/skills-config` — 스킬 설정
- `tools/plugin` — 플러그인
- `tools/subagents` — 서브에이전트
- `tools/browser` — 브라우저
- `tools/browser-login` — 브라우저 로그인
- `tools/browser-linux-troubleshooting` — 브라우저 Linux 트러블슈팅
- `tools/chrome-extension` — Chrome 확장
- `tools/exec` — 실행
- `tools/elevated` — 권한 상승
- `tools/web` — 웹
- `tools/llm-task` — LLM 작업
- `tools/agent-send` — 에이전트 메시지
- `tools/apply-patch` — 패치 적용
- `tools/reactions` — 리액션
- `tools/slash-commands` — 슬래시 커맨드
- `tools/thinking` — 씽킹
- `tools/clawhub` — ClawHub
- `tools/lobster` — Lobster
- `tools/multi-agent-sandbox-tools` — 멀티에이전트 샌드박스

## Providers
- `providers/anthropic` — Anthropic
- `providers/openai` — OpenAI
- `providers/bedrock` — AWS Bedrock
- `providers/openrouter` — OpenRouter
- `providers/litellm` — LiteLLM
- `providers/vercel-ai-gateway` — Vercel AI Gateway
- `providers/minimax`, `moonshot`, `qianfan`, `glm`, `opencode`, `zai`, `synthetic`

## Platforms
- `platforms/ios` — iOS
- `platforms/android` — Android
- `platforms/linux` — Linux
- `platforms/macos` — macOS
- `platforms/windows` — Windows (WSL2)
- Mac 세부: `platforms/mac/bundled-gateway`, `canvas`, `permissions`, `voice-overlay`, `webchat`, `menu-bar`, `peekaboo`, `skills`, `remote`, `health`, `logging`, `signing`, `release`, `dev-setup`, `child-process`, `icon`, `voicewake`, `xpc`

## Nodes
- `nodes/audio` — 오디오
- `nodes/camera` — 카메라
- `nodes/images` — 이미지
- `nodes/location-command` — 위치
- `nodes/talk` — 대화 모드
- `nodes/voicewake` — 음성 웨이크
- `nodes/troubleshooting` — 노드 트러블슈팅

## Web
- `web/dashboard` — 대시보드
- `web/webchat` — 웹챗
- `web/control-ui` — 컨트롤 UI
- `web/tui` — TUI

## Reference
- `reference/templates/AGENTS.md` — AGENTS 템플릿
- `reference/templates/SOUL.md` — SOUL 템플릿
- `reference/templates/IDENTITY.md` — IDENTITY 템플릿
- `reference/templates/USER.md` — USER 템플릿
- `reference/templates/TOOLS.md` — TOOLS 템플릿
- `reference/templates/HEARTBEAT.md` — HEARTBEAT 템플릿
- `reference/templates/BOOT.md` — BOOT 템플릿
- `reference/templates/BOOTSTRAP.md` — BOOTSTRAP 템플릿
- `reference/AGENTS.default.md` — AGENTS 기본값
- `reference/credits` — 크레딧
- `reference/rpc` — RPC
- `reference/device-models` — 디바이스 모델
- `reference/token-use` — 토큰 사용량
- `reference/session-management-compaction` — 세션 컴팩션
- `reference/wizard` — 마법사
- `reference/test` — 테스트

## Help
- `help/faq` — FAQ
- `help/troubleshooting` — 트러블슈팅
- `help/debugging` — 디버깅
- `help/environment` — 환경
- `help/scripts` — 스크립트
- `help/testing` — 테스트
- `help/submitting-a-pr` — PR 제출
- `help/submitting-an-issue` — 이슈 제출
