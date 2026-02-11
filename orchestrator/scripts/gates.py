"""
Confirmation Gates for Agent OS Orchestrator
Implements policy defined in AGENTS.md § 2.5 gates, § 2.6 checkpoints, § 2.7 reapproval
"""
from typing import Dict, List, Optional, Union

def format_plan_confirmation(
    title: str,
    goal: str,
    steps: List[str],
    deliverable: str,
    eta_min: int,
    tokens_in_k: int,
    tokens_out_k: int
) -> str:
    """
    Format Gate 1: Plan Confirmation Message
    """
    # Limit to 3 bullets
    display_steps = steps[:3]
    bullets = "\n".join([f"• {step}" for step in display_steps])
    if len(steps) > 3:
        bullets += f"\n• ... (+{len(steps)-3} more)"

    return (
        f"**{title}**\n\n"
        f"🎯 **목표:** {goal}\n\n"
        f"**계획:**\n{bullets}\n\n"
        f"**산출물:** {deliverable}\n\n"
        f"ETA: ~{eta_min}min | 토큰: ~{tokens_in_k}K in / ~{tokens_out_k}K out\n\n"
        f"진행할까요?"
    )

def format_budget_confirmation(
    eta_min: int,
    tokens_in_k: int,
    tokens_out_k: int,
    cost_usd: float
) -> str:
    """
    Format Gate 2: Token Budget Confirmation Message
    """
    return (
        f"⚠️ **토큰 예산 확인**\n\n"
        f"이 작업은 Medium 크기입니다:\n"
        f"- 예상 소요: ~{eta_min}min\n"
        f"- 토큰 사용: ~{tokens_in_k}K in / ~{tokens_out_k}K out\n"
        f"- 예상 비용: ${cost_usd:.2f} (GPT-4 기준)\n\n"
        f"계속 진행할까요?"
    )

def check_approval(response: str) -> bool:
    """
    Check if user response indicates approval
    """
    if not response:
        return False
    
    # Normalize
    response = response.strip().lower()
    
    # Positive signals
    positive = ["진행", "ok", "yes", "go", "좋아", "y", "ㅇㅇ", "👍", "approve", "confirm"]
    
    return any(p in response for p in positive)

def ask_approval(
    title: str,
    goal: str,
    steps: List[str],
    deliverable: str,
    eta_min: int,
    tokens_in_k: int,
    tokens_out_k: int,
    cost_usd: Optional[float] = None,
    interactive: bool = False
) -> Union[bool, str]:
    """
    High-level approval flow.
    If interactive=True, prints and asks input.
    If interactive=False, returns the Gate 1 message string.
    
    Note: Gate 2 is separate.
    """
    msg = format_plan_confirmation(title, goal, steps, deliverable, eta_min, tokens_in_k, tokens_out_k)
    
    if interactive:
        print(msg)
        try:
            resp = input("\n> ")
            is_approved = check_approval(resp)
            
            if is_approved and cost_usd is not None and cost_usd >= 0.50:
                # Trigger Gate 2
                msg2 = format_budget_confirmation(eta_min, tokens_in_k, tokens_out_k, cost_usd)
                print("\n" + msg2)
                resp2 = input("\n> ")
                return check_approval(resp2)
            
            return is_approved
        except EOFError:
            return False
            
    return msg


# Example usage
if __name__ == "__main__":
    print("=== Confirmation Gates - Test ===\n")
    
    # Test 1: Format Gate 1
    print("Test 1: Gate 1 (Plan Confirmation)")
    msg1 = format_plan_confirmation(
        title="API 연동 작업",
        goal="Google Calendar와 로컬 YAML Tasks DB 동기화",
        steps=["API 인증 설정", "데이터 fetch 및 변환", "YAML 파일 업데이트", "에러 핸들링"],
        deliverable="YAML Tasks DB 업데이트 + 로그",
        eta_min=25,
        tokens_in_k=40,
        tokens_out_k=12
    )
    print(msg1)
    print()
    
    # Test 2: Format Gate 2
    print("Test 2: Gate 2 (Token Budget)")
    msg2 = format_budget_confirmation(
        eta_min=45,
        tokens_in_k=80,
        tokens_out_k=25,
        cost_usd=2.10
    )
    print(msg2)
    print()
    
    # Test 3: Check approval
    print("Test 3: Approval checking")
    test_responses = ["진행", "ok", "Yes", "cancel", "no", "👍"]
    for resp in test_responses:
        is_approved = check_approval(resp)
        print(f"  '{resp}' → {is_approved}")
    
    print("\n✅ Gates tests complete")
