#!/usr/bin/env python3
"""
Notion View Setup Helper
Generate view configuration for TASKS.md-style workflow
"""

import os
import sys
from pathlib import Path
from typing import List, Dict

DEFAULT_API_KEY_PATH = "~/.config/notion/api_key_daye_personal"
DEFAULT_TASKS_DB_ID = "8e0e8902-0c60-4438-8bbf-abe10d474b9b"


def get_notion_client(api_key_path: str = None):
    """Initialize Notion client"""
    try:
        from notion_client import Client
    except ImportError:
        print("❌ notion-client not installed. Run: pip3 install notion-client")
        sys.exit(1)
    
    if api_key_path is None:
        api_key_path = DEFAULT_API_KEY_PATH
    
    api_key_path = os.path.expanduser(api_key_path)
    if not os.path.exists(api_key_path):
        raise FileNotFoundError(f"Notion API key not found: {api_key_path}")
    
    with open(api_key_path) as f:
        api_key = f.read().strip()
    
    return Client(auth=api_key)


def analyze_tasks_db(db_id: str = None, api_key_path: str = None) -> Dict:
    """
    Analyze Tasks DB structure and current Status values
    
    Returns:
        {
            "database_id": str,
            "title": str,
            "properties": Dict,
            "status_options": List[str],
            "sample_tasks": List[Dict]
        }
    """
    try:
        notion = get_notion_client(api_key_path)
        
        if db_id is None:
            db_id = DEFAULT_TASKS_DB_ID
        
        # Get database schema
        db_response = notion.databases.retrieve(database_id=db_id)
        
        # Extract Status options
        status_property = db_response.get("properties", {}).get("Status", {})
        status_options = []
        if status_property.get("type") == "status":
            status_config = status_property.get("status", {})
            # Try both 'groups' and 'options' (API structure varies)
            if "groups" in status_config:
                for group in status_config["groups"]:
                    status_options.extend([opt["name"] for opt in group.get("options", [])])
            elif "options" in status_config:
                status_options = [opt["name"] for opt in status_config["options"]]
        
        # Query sample tasks
        tasks_response = notion.databases.query(
            database_id=db_id,
            page_size=10
        )
        
        sample_tasks = []
        for page in tasks_response.get("results", []):
            props = page["properties"]
            sample_tasks.append({
                "name": props.get("Name", {}).get("title", [{}])[0].get("text", {}).get("content", "Untitled"),
                "status": props.get("Status", {}).get("status", {}).get("name", "N/A"),
                "priority": props.get("Priority", {}).get("select", {}).get("name", "N/A")
            })
        
        return {
            "database_id": db_id,
            "title": db_response.get("title", [{}])[0].get("text", {}).get("content", "Untitled DB"),
            "properties": list(db_response["properties"].keys()),
            "status_options": status_options,
            "sample_tasks": sample_tasks
        }
    
    except Exception as e:
        return {
            "error": str(e),
            "database_id": db_id
        }


def generate_view_guide(analysis: Dict) -> str:
    """
    Generate Notion view setup guide based on DB analysis
    
    TASKS.md Style:
    - Active: Currently working on
    - Waiting On: Blocked or waiting for external input
    - Someday: Backlog/future work
    - Done: Completed tasks
    """
    
    status_options = analysis.get("status_options", [])
    
    # Map existing statuses to TASKS.md categories
    mapping = {
        "Active": ["In Progress", "Started", "Working"],
        "Waiting On": ["Blocked", "Waiting", "Paused"],
        "Someday": ["Not Started", "Backlog", "Planned"],
        "Done": ["Done", "Completed", "Archived"]
    }
    
    # Find matches
    matched = {category: [] for category in mapping.keys()}
    unmatched = []
    
    for status in status_options:
        matched_any = False
        for category, keywords in mapping.items():
            if any(keyword.lower() in status.lower() for keyword in keywords):
                matched[category].append(status)
                matched_any = True
                break
        if not matched_any:
            unmatched.append(status)
    
    # Generate guide
    guide = f"""
# Notion Tasks DB - TASKS.md 스타일 뷰 설정 가이드

**Database:** {analysis.get('title', 'Tasks')}
**Database ID:** `{analysis['database_id']}`

## 🎯 목표: anthropic TASKS.md 스타일 워크플로우

Anthropic의 TASKS.md처럼 4가지 카테고리로 작업 관리:
- **Active:** 지금 진행 중인 작업
- **Waiting On:** 외부 입력/블로커 대기 중
- **Someday:** 백로그/나중에 할 작업
- **Done:** 완료된 작업

## 📊 현재 DB Status 분석

**발견된 Status 옵션:** {len(status_options)}개
```
{chr(10).join(['- ' + s for s in status_options])}
```

## 🗂️ Status → Category 매핑

"""
    
    for category, statuses in matched.items():
        if statuses:
            guide += f"\n### {category}\n"
            guide += "```\n"
            guide += "\n".join([f"✅ {s}" for s in statuses])
            guide += "\n```\n"
    
    if unmatched:
        guide += f"\n### ⚠️ 매핑되지 않은 Status\n"
        guide += "```\n"
        guide += "\n".join([f"❓ {s}" for s in unmatched])
        guide += "\n```\n"
        guide += "\n**Action:** 이 Status들을 위 4가지 카테고리 중 하나로 매핑하세요.\n"
    
    guide += """

## 🛠️ Notion에서 뷰 생성하기

### Step 1: Board 뷰 생성
1. Tasks DB 열기
2. 우측 상단 `+ 새 보기` 클릭
3. **Board** 선택
4. 이름: `Claude-cowork (TASKS.md)`

### Step 2: Group by Status
1. 뷰 설정 열기 (우측 상단 `···` → `속성`)
2. **Group by:** `Status` 선택
3. **그룹 순서 조정:**
   - Active (진행 중)
   - Waiting On (대기)
   - Someday (백로그)
   - Done (완료)

### Step 3: 필터 설정 (선택사항)
**Completed 작업 숨기기:**
```
Status ≠ Done
```

**최근 7일 작업만 표시:**
```
Start Date > 7 days ago
```

### Step 4: 정렬 설정
1. **Sort by:**
   - Primary: `Priority` (P1 → P4)
   - Secondary: `Start Date` (최신순)

### Step 5: 표시 속성 선택
체크:
- [x] Name
- [x] Owner
- [x] Priority
- [x] Start Date
- [x] Due
- [ ] Tags (선택)
- [ ] Project (선택)

숨김:
- [ ] Created time
- [ ] Last edited

### Step 6: 기본 뷰로 설정
1. 뷰 설정 → `기본 보기로 설정`
2. 모든 팀원이 이 뷰를 기본으로 보게 됨

## 🎨 보드 커스터마이징 (선택사항)

### 컬러 코딩
- **Active:** 파란색 배경
- **Waiting On:** 노란색 배경
- **Someday:** 회색 배경
- **Done:** 초록색 배경

**설정 방법:**
1. 각 Status 그룹 제목 클릭
2. `배경색 선택`

### 그룹 접기/펼치기
- **Done 그룹:** 기본으로 접기 (완료 작업 숨김)
- 필요 시 클릭해서 펼치기

## 📝 운영 가이드

### 일일 루틴
**아침:**
1. **Active** 그룹 확인: 오늘 집중할 작업 3개 이하 유지
2. **Waiting On** 체크: 블로커 해소 가능한 것 확인

**저녁:**
1. 완료한 작업 → **Done**으로 이동
2. 내일 작업 1-2개를 **Someday** → **Active**로 이동

### 주간 루틴
**금요일 회고:**
1. **Done** 그룹 리뷰: 이번 주 성과 확인
2. **Someday** 정리: 불필요한 작업 Archive
3. **Waiting On** 점검: 1주일 이상 대기 중이면 에스컬레이션

## 🤖 자동화 제안

### Status 자동 전환
- [ ] Start Date 설정 시 → **Active**로 자동 변경
- [ ] Due 지난 작업 → **Blocked** 알림
- [ ] Done 후 7일 → 자동 Archive

**구현:** `skills/task-policy/automation/` 참고

### Agent 통합
- [ ] Agent가 작업 시작 시 자동으로 **Active** 설정
- [ ] 서브에이전트 spawn 시 Task 링크 필수
- [ ] 완료 시 자동으로 **Done** + 산출물 링크

**구현:** AGENTS.md § 7 참고

## 📚 참고 자료
- **Anthropic TASKS.md:** https://github.com/anthropics/anthropic-cookbook
- **Task-Centric Policy:** `skills/task-policy/POLICY.md`
- **Notion API:** https://developers.notion.com

## 🆘 문제 해결

### "Status 옵션이 안 보여요"
- Tasks DB 설정 → 속성 → Status → 옵션 추가

### "그룹 순서를 못 바꾸겠어요"
- Board 뷰에서 그룹 제목을 드래그해서 순서 변경

### "필터가 작동 안 해요"
- 필터 조건 확인 (AND/OR 구분)
- 날짜 형식 확인 (ISO 8601)

---

**생성일:** {analysis.get('generated_at', 'N/A')}
**DB ID:** `{analysis['database_id']}`
"""
    
    return guide


if __name__ == "__main__":
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="Notion View Setup Helper")
    parser.add_argument("--db-id", default=DEFAULT_TASKS_DB_ID, help="Tasks DB ID")
    parser.add_argument("--output", default="NOTION_VIEW_GUIDE.md", help="Output file")
    
    args = parser.parse_args()
    
    print("📊 Analyzing Tasks DB...\n")
    analysis = analyze_tasks_db(db_id=args.db_id)
    
    if "error" in analysis:
        print(f"❌ Error: {analysis['error']}")
        sys.exit(1)
    
    print(f"✅ Database: {analysis['title']}")
    print(f"   Properties: {len(analysis['properties'])}")
    print(f"   Status Options: {len(analysis['status_options'])}")
    print(f"   Sample Tasks: {len(analysis['sample_tasks'])}\n")
    
    # Generate guide
    analysis["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    guide = generate_view_guide(analysis)
    
    # Write to file
    output_path = Path(args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(guide)
    
    print(f"📝 Guide generated: {output_path}")
    print(f"\n🔗 Open in Notion: https://notion.so/{args.db_id.replace('-', '')}")
