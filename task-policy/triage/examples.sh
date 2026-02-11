#!/bin/bash
# Task Triage Skill - Usage Examples

echo "=== Task Triage Skill Examples ==="
echo ""

# Example 1: Simple Task (Dry-Run)
echo "1. Simple Task Classification (Dry-Run)"
echo "   Command: python3 skills/task-triage/triage.py '토스 API 문서 리뷰'"
echo "   Expected: Task (90%+ confidence), no Notion write"
echo ""
python3 skills/task-triage/triage.py "토스 API 문서 리뷰"
echo ""
echo "---"
echo ""

# Example 2: Project Classification
echo "2. Project Classification"
echo "   Command: python3 skills/task-triage/triage.py '토스 API 연동 구현'"
echo "   Expected: Project (75%+ confidence)"
echo ""
python3 skills/task-triage/triage.py "토스 API 연동 구현"
echo ""
echo "---"
echo ""

# Example 3: Follow-Up Detection
echo "3. Follow-Up Work Detection"
echo "   Command: python3 skills/task-triage/triage.py '가이드 v2 개선 작업'"
echo "   Expected: Task, is_followup=True"
echo ""
python3 skills/task-triage/triage.py "가이드 v2 개선 작업"
echo ""
echo "---"
echo ""

# Example 4: Epic (Explicit)
echo "4. Epic Classification"
echo "   Command: python3 skills/task-triage/triage.py '로닉 플랫폼 전략 수립'"
echo "   Expected: Epic or Project (depends on keywords)"
echo ""
python3 skills/task-triage/triage.py "로닉 플랫폼 전략 수립"
echo ""
echo "---"
echo ""

# Example 5: Override Classification
echo "5. Manual Override"
echo "   Command: python3 skills/task-triage/triage.py '애매한 요청' --override-classification Task"
echo "   Expected: Task (forced)"
echo ""
python3 skills/task-triage/triage.py "애매한 요청" --override-classification Task
echo ""
echo "---"
echo ""

echo "=== All Examples Complete ==="
echo ""
echo "To execute with Notion writes:"
echo "  python3 skills/task-triage/triage.py 'request' --execute"
echo ""
echo "To auto-approve (skip prompt):"
echo "  python3 skills/task-triage/triage.py 'request' --auto-approve"
