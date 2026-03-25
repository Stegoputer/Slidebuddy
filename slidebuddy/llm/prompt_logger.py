"""Debug prompt logger — writes every LLM call to a JSON-Lines file.

Enable via preferences: set "debug_prompts" to True in settings.
Log file: data/prompt_debug.jsonl (one JSON object per line per LLM call).
"""

import json
import time
from datetime import datetime
from pathlib import Path

from slidebuddy.config.defaults import DATA_DIR, load_preferences

LOG_PATH = DATA_DIR / "prompt_debug.jsonl"


def is_debug_enabled() -> bool:
    return load_preferences().get("debug_prompts", False)


def log_llm_call(
    phase: str,
    system_prompt: str,
    user_prompt: str,
    response_text: str,
    duration_s: float,
    chunks: list[dict] | None = None,
    metadata: dict | None = None,
):
    """Append one LLM call record to the debug log."""
    if not is_debug_enabled():
        return

    # Rough token estimate (1 token ≈ 4 chars for German)
    sys_chars = len(system_prompt)
    usr_chars = len(user_prompt)
    resp_chars = len(response_text)
    est_input_tokens = (sys_chars + usr_chars) // 4
    est_output_tokens = resp_chars // 4

    record = {
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        "system_prompt_chars": sys_chars,
        "user_prompt_chars": usr_chars,
        "response_chars": resp_chars,
        "est_input_tokens": est_input_tokens,
        "est_output_tokens": est_output_tokens,
        "duration_s": round(duration_s, 2),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "response": response_text,
        "chunks_count": len(chunks) if chunks else 0,
        "chunks": [
            {
                "text": c.get("text", "")[:500],
                "full_length": len(c.get("text", "")),
                "metadata": c.get("metadata", {}),
            }
            for c in (chunks or [])
        ],
        **(metadata or {}),
    }

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def clear_log():
    """Delete the debug log file."""
    if LOG_PATH.exists():
        LOG_PATH.unlink()


def read_log() -> list[dict]:
    """Read all logged LLM calls."""
    if not LOG_PATH.exists():
        return []
    records = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def get_log_summary() -> dict:
    """Return aggregate stats from the debug log."""
    records = read_log()
    if not records:
        return {"total_calls": 0}

    total_input = sum(r["est_input_tokens"] for r in records)
    total_output = sum(r["est_output_tokens"] for r in records)
    total_duration = sum(r["duration_s"] for r in records)

    by_phase = {}
    for r in records:
        p = r["phase"]
        if p not in by_phase:
            by_phase[p] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "duration_s": 0}
        by_phase[p]["calls"] += 1
        by_phase[p]["input_tokens"] += r["est_input_tokens"]
        by_phase[p]["output_tokens"] += r["est_output_tokens"]
        by_phase[p]["duration_s"] += r["duration_s"]

    return {
        "total_calls": len(records),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_duration_s": round(total_duration, 1),
        "by_phase": by_phase,
    }
