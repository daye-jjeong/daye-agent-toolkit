#!/usr/bin/env python3
"""
Example: Session completion handler with guardrails validation.
Uses Obsidian vault for deliverable storage.
"""

import sys
from pathlib import Path
from typing import Dict, List

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from guardrails.lib.gates import post_work_gate
from guardrails.lib.deliverable_checker import detect_created_files


def complete_with_guardrails(
    session_id: str,
    final_output: str,
    work_dir: Path = None,
    auto_upload: bool = True,
    model: str = "unknown"
) -> Dict:
    """
    Complete session with guardrails validation.

    Args:
        session_id: Session identifier
        final_output: Subagent's final report/output
        work_dir: Working directory to check for created files
        auto_upload: Auto-save deliverables to vault
        model: AI model used (for footer metadata)

    Returns:
        {
            "gate_result": Dict,
            "can_archive": bool,
            "action_required": str | None
        }
    """
    # Detect created files if work_dir provided
    created_files = None
    if work_dir:
        created_files = detect_created_files(work_dir)
        if created_files:
            print(f"Detected {len(created_files)} created files:")
            for f in created_files:
                print(f"   - {f}")

    # Run post-work gate
    gate_result = post_work_gate(
        session_id=session_id,
        final_output=final_output,
        created_files=created_files,
        auto_upload=auto_upload,
        model=model
    )

    print(f"\nPost-work gate: {gate_result['message']}")

    # Check if saved any deliverables
    if gate_result.get("uploaded"):
        print(f"Auto-saved {len(gate_result['uploaded'])} deliverables to vault:")
        for upload in gate_result["uploaded"]:
            print(f"   - {upload['original_path']}")
            print(f"     -> {upload['vault_path']}")

    # Determine if can archive
    can_archive = gate_result["passed"]
    action_required = gate_result.get("action_required")

    if can_archive:
        print(f"Session can be archived")
    else:
        print(f"Session should NOT be archived yet")
        if action_required:
            print(f"   Action required: {action_required}")

    return {
        "gate_result": gate_result,
        "can_archive": can_archive,
        "action_required": action_required
    }


def example_usage():
    """Example usage of guardrails-wrapped completion"""

    print("=== Guardrails Completion Examples ===\n")

    # Example 1: Work with accessible deliverables (should pass)
    print("Example 1: Work with accessible vault deliverables")

    final_output_1 = """
    ## 작업 완료

    AI 트렌드 분석을 완료했습니다.

    ## 산출물
    - vault 리포트: [[ai-trends-report-2026]]
    - 데이터: https://example.com/charts

    ## 참고
    추가 자료는 Task 페이지에 첨부했습니다.
    """

    result = complete_with_guardrails(
        session_id="agent:main:subagent:example-1",
        final_output=final_output_1,
        auto_upload=False,
        model="anthropic/claude-sonnet-4-5"
    )
    print()

    # Example 2: Work with local files (should auto-save if enabled)
    print("Example 2: Work with local deliverables (auto-save to vault)")

    final_output_2 = """
    ## 작업 완료

    가이드 문서를 작성했습니다.

    ## 산출물
    - 가이드: [완전한 가이드](./docs/complete_guide.md)
    - 설정 파일: ./config/settings.json

    ## 참고
    로컬 파일로 생성되었습니다.
    """

    result = complete_with_guardrails(
        session_id="agent:main:subagent:example-2",
        final_output=final_output_2,
        work_dir=Path.cwd(),
        auto_upload=False,
        model="anthropic/claude-sonnet-4-5"
    )
    print()

    # Example 3: Work with no deliverables (should warn)
    print("Example 3: Work with no deliverables (should warn)")

    final_output_3 = """
    ## 작업 완료

    분석을 수행했습니다.

    ## 결론
    모든 시스템이 정상 작동 중입니다.
    """

    result = complete_with_guardrails(
        session_id="agent:main:subagent:example-3",
        final_output=final_output_3,
        auto_upload=False,
        model="anthropic/claude-sonnet-4-5"
    )
    print()


if __name__ == "__main__":
    example_usage()
