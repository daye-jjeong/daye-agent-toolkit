---
name: task-dashboard
description: 프로젝트 태스크(t-{project}-NNN.md) + goals YAML → 인터랙티브 HTML 대시보드
metadata: {"openclaw":{"requires":{"bins":["python3"]}}}
---

# Task Dashboard Skill

## Description
프로젝트별 태스크 파일(t-{project}-NNN.md)과 goals YAML을 결합하여 인터랙티브 HTML 대시보드를 생성합니다.

## Version
0.4.0

## Usage

```bash
python3 {baseDir}/generate_dashboard_v3.py
```

### Configuration
`config.json`:
- `projects_root`: 프로젝트 디렉토리 경로
- `goals_root`: 목표 디렉토리 경로 (기본: `projects/_goals`)
- `output_dir`: HTML 출력 경로
- `language`: UI 언어 (`ko`)

### Output
단일 self-contained HTML 파일. 브라우저에서 바로 열 수 있음.

## Features
- **오늘의 포커스 히어로**: Top 3 + 골 체인 (월간 → 주간 → 오늘)
- **시간 블록 / 체크리스트**: 별도 카드로 분리 표시
- **월간/주간 목표 카드**: 진행률 + KR 상세
- **태스크 테이블**: 프로젝트/담당자/상태/우선순위 필터, 정렬
- **프로젝트 상세 모달**: 클릭 시 설명, 연결 목표, 작업 현황, 히스토리
- **담당자별 차트**: 상태 분포 시각화
- 반응형 디자인 (모바일/데스크톱)

## Dependencies
- Python 3.8+
- PyYAML
