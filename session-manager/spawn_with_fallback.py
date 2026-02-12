#!/usr/bin/env python3
"""
Session Spawning with Automatic Fallback/Retry Logic

Handles model selection fallback when spawning subagents:
- Rate limits (HTTP 429)
- Timeouts
- Model unavailable errors

Default fallback order:
  gpt-5.2 -> claude-sonnet-4-5 -> gemini-3-pro -> claude-haiku-4-5
  
Applies partial substitution (only failing worker) and logs all fallback decisions.
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum


class SpawnError(Enum):
    """Types of spawn errors that trigger fallback"""
    RATE_LIMIT = "rate_limit"  # HTTP 429
    TIMEOUT = "timeout"
    MODEL_UNAVAILABLE = "model_unavailable"
    UNKNOWN = "unknown"


# Default fallback chain (can be overridden in plan)
DEFAULT_FALLBACK_ORDER = [
    "openai-codex/gpt-5.2",
    "anthropic/claude-sonnet-4-5",
    "google-gemini-3-pro",
    "anthropic/claude-haiku-4-5"
]


def classify_error(error_output: str, return_code: int) -> SpawnError:
    """
    Classify spawn error type from command output
    
    Args:
        error_output: stderr/stdout from failed spawn
        return_code: Process exit code
        
    Returns:
        SpawnError enum value
    """
    error_lower = error_output.lower()
    
    # Check for rate limit (429)
    if "429" in error_output or "rate limit" in error_lower or "too many requests" in error_lower:
        return SpawnError.RATE_LIMIT
    
    # Check for timeout
    if "timeout" in error_lower or "timed out" in error_lower:
        return SpawnError.TIMEOUT
    
    # Check for model unavailable
    if "model" in error_lower and any(
        kw in error_lower for kw in ["unavailable", "not found", "not available", "doesn't exist"]
    ):
        return SpawnError.MODEL_UNAVAILABLE
    
    return SpawnError.UNKNOWN


def log_fallback_decision(
    original_model: str,
    fallback_model: str,
    error_type: SpawnError,
    attempt: int,
    max_attempts: int,
    task_label: str,
    reason: str = None
) -> None:
    """
    Log fallback decision to file for audit trail
    
    Args:
        original_model: Model that failed
        fallback_model: Model to try next
        error_type: Type of error encountered
        attempt: Current attempt number
        max_attempts: Maximum retry attempts
        task_label: Session label
        reason: Optional detailed reason
    """
    log_dir = Path.home() / ".clawdbot" / "agents" / "main" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "fallback_decisions.jsonl"
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_label": task_label,
        "original_model": original_model,
        "fallback_model": fallback_model,
        "error_type": error_type.value,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "reason": reason or f"{error_type.value} detected"
    }
    
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    print(f"⚠️  Fallback: {original_model} → {fallback_model} ({error_type.value}, attempt {attempt}/{max_attempts})")


def spawn_subagent_with_retry(
    task: str,
    model: str,
    label: str,
    fallback_order: Optional[List[str]] = None,
    max_retries: int = 3,
    retry_delay: int = 5,
    current_depth: int = 0,
    task_url: Optional[str] = None,
    **kwargs
) -> Dict:
    """
    Spawn subagent with automatic model fallback on failure
    
    Args:
        task: Task description
        model: Initial model to try
        label: Session label
        fallback_order: Custom fallback chain (None = use DEFAULT_FALLBACK_ORDER)
        max_retries: Maximum number of retry attempts per model
        retry_delay: Seconds to wait between retries (for rate limits)
        current_depth: Current nesting depth (0=Main, 1=Sub). Max allowed is 1 (resulting in depth 2).
        task_url: Task URL for linkage enforcement
        **kwargs: Additional spawn parameters
        
    Returns:
        Dict: Spawn result
        
    Raises:
        ValueError: If depth limit exceeded or task URL missing
        Exception: If all models in fallback chain fail
    """
    # --- Agent OS Policy Enforcement ---
    
    # 1. 2-Level Depth Limit Check
    # We allow spawning IF current_depth < 2.
    # Depth 0 (Main) -> Spawns Depth 1 (Sub) -> OK
    # Depth 1 (Sub) -> Spawns Depth 2 (Sub-Sub) -> OK (but Depth 2 cannot spawn)
    # Depth 2 (Sub-Sub) -> Spawns Depth 3 -> BLOCK
    # Policy: "2-level Depth Limit" usually implies max depth 2.
    next_depth = current_depth + 1
    if next_depth > 2:
        raise ValueError(f"Agent OS Policy: Depth limit exceeded. Max depth 2, requested {next_depth}. (Current: {current_depth})")

    # 2. Task Linkage Enforcement
    # Must have Task URL if not trivial (we assume non-trivial if spawning agent)
    has_url = task_url or ("https://notion.so" in task)
    if not has_url:
        # Check if explicitly allowed to bypass (e.g. trivial) - strictly enforcing per prompt
        raise ValueError("Agent OS Policy: Task URL required for spawning subagent (Task Linkage). Please create a Task first.")

    # -----------------------------------

    if fallback_order is None:
        fallback_order = DEFAULT_FALLBACK_ORDER.copy()
    
    # Ensure requested model is first in chain
    if model not in fallback_order:
        fallback_order.insert(0, model)
    else:
        # Move requested model to front
        fallback_order.remove(model)
        fallback_order.insert(0, model)
    
    attempted_models = []
    total_attempts = 0
    last_error = None
    
    for model_idx, current_model in enumerate(fallback_order):
        for attempt in range(1, max_retries + 1):
            total_attempts += 1
            attempted_models.append(current_model)
            
            try:
                # Build spawn command
                cmd = [
                    "clawdbot", "sessions", "spawn",
                    "--label", label,
                    "--model", current_model,
                    task
                ]
                
                # Execute spawn
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Check success
                if result.returncode == 0:
                    # Extract session ID from output (parse sessions list)
                    # Format: "direct agent:main:subag...xxx"
                    session_id = None
                    for line in result.stdout.split("\n"):
                        if "agent:main:subag" in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                session_id = parts[1]
                                break
                    
                    print(f"✅ Subagent spawned successfully: {session_id or 'unknown'}")
                    print(f"   Model: {current_model} (attempt {total_attempts})")
                    
                    return {
                        "success": True,
                        "session_id": session_id,
                        "model_used": current_model,
                        "attempts": total_attempts,
                        "fallback_chain": attempted_models,
                        "error": None
                    }
                
                # Spawn failed - classify error
                error_output = result.stdout + result.stderr
                error_type = classify_error(error_output, result.returncode)
                last_error = error_output
                
                # Check if we should try next model or retry same model
                if error_type == SpawnError.RATE_LIMIT and attempt < max_retries:
                    # Retry same model after delay
                    print(f"⏳ Rate limit hit, waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                    continue
                
                elif error_type == SpawnError.MODEL_UNAVAILABLE:
                    # Model doesn't exist - immediately try next
                    if model_idx < len(fallback_order) - 1:
                        next_model = fallback_order[model_idx + 1]
                        log_fallback_decision(
                            original_model=current_model,
                            fallback_model=next_model,
                            error_type=error_type,
                            attempt=attempt,
                            max_attempts=max_retries,
                            task_label=label,
                            reason=f"Model unavailable: {current_model}"
                        )
                    break  # Exit retry loop for this model
                
                elif attempt < max_retries:
                    # Generic retry with backoff
                    print(f"⚠️  Spawn failed, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                
                else:
                    # Exhausted retries for this model
                    if model_idx < len(fallback_order) - 1:
                        next_model = fallback_order[model_idx + 1]
                        log_fallback_decision(
                            original_model=current_model,
                            fallback_model=next_model,
                            error_type=error_type,
                            attempt=attempt,
                            max_attempts=max_retries,
                            task_label=label,
                            reason=f"Max retries exhausted"
                        )
                    break  # Exit retry loop for this model
            
            except subprocess.TimeoutExpired:
                # Command timed out
                error_type = SpawnError.TIMEOUT
                last_error = "Command execution timeout"
                
                if attempt < max_retries:
                    print(f"⏳ Spawn timeout, retrying...")
                    continue
                else:
                    if model_idx < len(fallback_order) - 1:
                        next_model = fallback_order[model_idx + 1]
                        log_fallback_decision(
                            original_model=current_model,
                            fallback_model=next_model,
                            error_type=error_type,
                            attempt=attempt,
                            max_attempts=max_retries,
                            task_label=label
                        )
                    break
            
            except Exception as e:
                last_error = str(e)
                print(f"❌ Unexpected error: {e}")
                break
    
    # All models failed - notify user
    print(f"❌ All models in fallback chain failed after {total_attempts} attempts")
    print(f"   Tried: {' -> '.join(attempted_models)}")
    
    # Send user notification (rate-limited to prevent spam)
    notify_script = Path.home() / "openclaw" / "scripts" / "notify_model_failure.sh"
    if notify_script.exists():
        try:
            subprocess.run([str(notify_script)], timeout=10, capture_output=True)
        except Exception as e:
            print(f"⚠️  Failed to send notification: {e}")
    
    return {
        "success": False,
        "session_id": None,
        "model_used": None,
        "attempts": total_attempts,
        "fallback_chain": attempted_models,
        "error": last_error
    }


def spawn_parallel_workers_with_fallback(
    tasks: List[Dict[str, str]],
    fallback_order: Optional[List[str]] = None,
    partial_substitution: bool = True
) -> Dict:
    """
    Spawn multiple parallel workers with fallback (Orchestrator use case)
    
    Args:
        tasks: List of task dicts with keys: "task", "model", "label"
        fallback_order: Custom fallback chain
        partial_substitution: If True, only retry failing workers (not all)
        
    Returns:
        {
            "success": bool,
            "workers": List[Dict],  # Result from each spawn
            "failed": List[str],    # Labels of failed workers
            "fallback_applied": int # Count of fallback substitutions
        }
    """
    workers = []
    failed = []
    fallback_count = 0
    
    for task_spec in tasks:
        result = spawn_subagent_with_retry(
            task=task_spec["task"],
            model=task_spec["model"],
            label=task_spec["label"],
            fallback_order=fallback_order
        )
        
        workers.append(result)
        
        if not result["success"]:
            failed.append(task_spec["label"])
        
        if result["model_used"] != task_spec["model"]:
            fallback_count += 1
    
    return {
        "success": len(failed) == 0,
        "workers": workers,
        "failed": failed,
        "fallback_applied": fallback_count
    }


# Example usage
if __name__ == "__main__":
    print("=== Session Spawn with Fallback - Test ===\n")
    
    # Test 1: Single worker spawn
    print("Test 1: Spawn single worker")
    result = spawn_subagent_with_retry(
        task="테스트 작업: 간단한 데이터 fetch",
        model="anthropic/claude-sonnet-4-5",
        label="test-single-worker"
    )
    print(f"Result: {json.dumps(result, indent=2)}\n")
    
    # Test 2: Parallel workers (Orchestrator scenario)
    print("Test 2: Spawn parallel workers")
    tasks = [
        {"task": "데이터 수집", "model": "google-gemini-flash", "label": "worker-1"},
        {"task": "분석 작업", "model": "anthropic/claude-sonnet-4-5", "label": "worker-2"},
        {"task": "리포트 작성", "model": "anthropic/claude-opus-4", "label": "worker-3"}
    ]
    
    result = spawn_parallel_workers_with_fallback(tasks)
    print(f"Result: {json.dumps(result, indent=2, ensure_ascii=False)}\n")
    
    print("✅ Tests complete. Check ~/.clawdbot/agents/main/logs/fallback_decisions.jsonl for logs")
