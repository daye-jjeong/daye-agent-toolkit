# Task Manager - 자동 재개 시스템

**Version:** 0.1.0
**Updated:** 2026-02-09
**Status:** Experimental

## 목적

실패하거나 중단된 작업을 자동으로 재개하면서 복잡도에 맞는 모델을 선택합니다. VIP Lane 보호를 통해 메인 세션의 API 할당량을 보호합니다.

## 주요 기능

### 1. VIP Lane 보호
- **Max 3개 동시 작업**: 백그라운드 작업 제한
- **시스템 부하 감시**: 80% 이상 시 작업 연기
- **모델 강제 선택**: 각 복잡도에 맞는 모델만 사용

### 2. 적응형 모델 선택

| 복잡도 | 모델 | 사용 시점 |
|--------|------|---------|
| simple | Gemini Flash, Haiku | API 호출, 데이터 조회 |
| moderate | Sonnet | 사용자 비활성 상태만 |
| complex | Opus 4.5 | 복잡한 추론 필요 작업 |

### 3. 지능형 재시도 로직
- **지수 백오프**: 1분 → 2분 → 4분
- **최대 3회 시도**: 초과 시 fallback alert
- **스마트 사용자 감지**: 메인 세션 활성 여부 확인

### 4. 작업 큐 관리
- 저장 위치: `memory/pending_tasks.json` (JSON 형식)
- FIFO 처리 + 우선순위 지원
- 재시작 후에도 지속

## 사용 방법

### 메인 에이전트에서 호출 (Heartbeat)

```javascript
// Heartbeat 로직에서
const result = execSync('node skills/task-manager/index.js 2>&1', { encoding: 'utf8' });
const jsonMatch = result.match(/\{.*\}/);

if (jsonMatch) {
  const status = JSON.parse(jsonMatch[0]);

  if (status.status === 'READY') {
    // 추천된 모델로 작업 실행
    const rec = status.recommendation;
    sessions_spawn({
      message: rec.prompt,
      model: rec.model
    });

    // 큐에서 제거
    execSync('node skills/task-manager/process-task.js');
  }
}
```

### 수동 실행

```bash
node skills/task-manager/index.js
```

### 작업 추가

```bash
./add-task.sh "작업 설명 또는 프롬프트"
```

또는 프로그래매틱하게:

```javascript
const tasks = require('./skills/task-manager');
const pending = tasks.loadPendingTasks();

pending.push({
  prompt: '분석 작업...',
  complexity: 'moderate',
  priority: 1
});

tasks.savePendingTasks(pending);
```

### 큐 확인

```bash
cat memory/pending_tasks.json | jq
```

## 설정

`index.js`의 CONFIG 섹션 수정:

```javascript
const CONFIG = {
  PENDING_TASKS_FILE: path.join(__dirname, '../../memory/pending_tasks.json'),
  LOCK_FILE: path.join(__dirname, '../../memory/task-manager.lock'),

  MAX_CONCURRENT_TASKS: 3,  // VIP Lane 한계
  MAX_LOAD_THRESHOLD: 80,   // 시스템 부하 한계 (%)

  MODELS: {
    simple: ['google-gemini-flash', 'claude-haiku-4-5'],
    moderate: 'claude-sonnet-4-5',
    complex: 'claude-opus-4-5'
  },

  MAX_RETRY_ATTEMPTS: 3,
  RETRY_BACKOFF_BASE_MS: 60000,      // 1분 기본 지연
  RETRY_BACKOFF_MULTIPLIER: 2         // 지수: 1분, 2분, 4분
};
```

## 작업 스키마

```json
{
  "prompt": "작업 설명 또는 프롬프트",
  "complexity": "simple|moderate|complex",
  "priority": 1,
  "metadata": {
    "source": "heartbeat",
    "retry_count": 0
  },
  "attempts": 0,
  "maxAttempts": 3,
  "nextRetryAt": "2026-02-01T12:05:00Z",
  "lastError": "이전 시도 에러 메시지"
}
```

### 필수 필드
- `prompt`: 작업 설명 (또는 `description`, `task`)
- `complexity`: 모델 선택 결정 요소

### 선택 필드
- `priority`: 우선순위 (기본값: 1)
- `metadata`: 추가 컨텍스트
- `maxAttempts`: 최대 시도 횟수 (기본값: 3)

## 안전 메커니즘

1. **Lock File** - 다중 인스턴스 실행 방지
2. **Concurrency Limit** - 동시 작업 수 제한 (Max 3)
3. **System Load Check** - 부하 > 80% 시 연기
4. **Model Enforcement** - 복잡도별 정해진 모델만 사용
5. **User-Quiet Detection** - 메인 세션 활성 여부 체크
6. **Exponential Backoff** - 실패 시 점진적 재시도

## 모니터링

로그는 stdout에 타임스탬프와 함께 출력됩니다:

```
[2026-02-01T12:00:00.000Z] [INFO] Loaded 3 pending task(s)
[2026-02-01T12:00:01.000Z] [WARN] Max concurrent tasks reached (3/3)
[2026-02-01T12:00:01.000Z] [INFO] VIP Lane protected: deferring new tasks
```

### 로그 레벨
- `INFO` - 일반 정보 (정상 흐름)
- `WARN` - 경고 (제한 도달, 작업 연기)
- `ERROR` - 오류 (API 실패, 최대 시도 초과)
- `DEBUG` - 디버그 (상세 정보)

## 출력 형식

### Ready (작업 준비됨)

```json
{
  "status": "READY",
  "recommendation": {
    "model": "google-gemini-flash",
    "prompt": "작업 설명",
    "complexity": "simple",
    "metadata": {},
    "priority": 1
  },
  "pending_count": 3,
  "message": "Ready to spawn task with google-gemini-flash"
}
```

### Deferred (작업 연기됨)

```json
{
  "status": "DEFERRED",
  "reason": "concurrency_limit",
  "pending_count": 3,
  "active_sessions": 3
}
```

## 모델 선택 로직

```javascript
selectModel(complexity) {
  if (complexity === 'simple') {
    return 'google-gemini-flash';
  }

  if (complexity === 'moderate') {
    // 사용자가 활성 상태면 downgrade
    return isUserQuiet() ? 'claude-sonnet-4-5' : 'google-gemini-flash';
  }

  if (complexity === 'complex') {
    return 'claude-opus-4-5'; // VIP lane 보호
  }
}
```

## 모듈 API

다른 스크립트에서 사용:

```javascript
const {
  main,
  loadPendingTasks,
  savePendingTasks,
  handleTaskFailure,
  calculateNextRetry
} = require('./skills/task-manager');

// 작업 로드
const tasks = loadPendingTasks();

// 실패 처리
const retryTask = handleTaskFailure(task, error);

// 저장
savePendingTasks(updatedTasks);
```

## 문제 해결

**작업이 실행되지 않음**
- Lock 파일 확인: `memory/task-manager.lock`
- 활성 세션 확인: `clawdbot sessions --active 30`
- 시스템 부하 확인: 80% 이상이면 작업 연기

**잘못된 모델 사용**
- `complexity` 필드 확인
- 로그에서 모델 선택 이유 확인
- 사용자 활성 여부 감지 로직 검증

**VIP Lane이 항상 가득 참**
- `MAX_CONCURRENT_TASKS` 증가 (신중하게)
- 오래된 백그라운드 세션 확인
- 작업 완료 여부 검증

## Heartbeat 통합

메인 에이전트의 heartbeat 체크에 추가:
- 5분마다 작업 관리자 실행
- 대기 중인 작업 확인
- 준비 상태면 새 세션 생성

## 모범 사례

1. **Simple** - API 호출, 데이터 조회, 반복 작업
2. **Moderate** - 요약, 기본 분석, 추천 (사용자 비활성 시만)
3. **Complex** - 리팩토링, 아키텍처 결정, 심층 분석

## 파일 구조

```
skills/task-manager/
├── index.js              # 메인 작업 관리자
├── process-task.js       # 작업 제거 헬퍼
├── add-task.sh           # 작업 추가 스크립트
├── check-and-spawn.sh    # 체크 및 실행 스크립트
├── README.md             # 이 문서
├── SKILL.md              # 스킬 매니페스트
├── CHANGELOG.md          # 버전 히스토리
├── VERSION               # 현재 버전
└── TEMPLATES.md          # 작업 템플릿 (레거시 Notion)
```

## 참고

- **Task Queue**: `memory/pending_tasks.json` (JSON 형식, YAML로 마이그레이션 가능)
- **Lock File**: `memory/task-manager.lock` (동시 실행 방지)
- **모델 선택**: 현재 6가지 모델 지원 (OpenAI, Anthropic, Google)
