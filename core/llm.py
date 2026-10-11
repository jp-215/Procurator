"""Anthropic wrapper: every call captures token usage into the metrics time
series and respects the run budget. No agent calls the API directly.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

import anthropic

from core.config import config
from core.metrics import record_turn, tokens_spent


class BudgetExhausted(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config().anthropic_api_key)


def ask(
    agent: str,
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = 4096,
    sprint: int = 0,
    ticket: str | None = None,
    retrieval_hits: int = 0,
) -> str:
    cfg = config()
    spent = tokens_spent(cfg.run_id)
    if spent >= cfg.budget_total_tokens:
        raise BudgetExhausted(f"{spent} >= {cfg.budget_total_tokens}")

    resp = _client().messages.create(
        model=model or cfg.worker_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    record_turn(
        run_id=cfg.run_id,
        agent=agent,
        sprint=sprint,
        ticket=ticket,
        tokens_in=resp.usage.input_tokens,
        tokens_out=resp.usage.output_tokens,
        retrieval_hits=retrieval_hits,
    )
    return text


def ask_json(agent: str, system: str, user: str, **kw) -> Any:
    """ask() + robust JSON extraction (handles fenced and bare JSON)."""
    text = ask(agent, system + "\nRespond ONLY with valid JSON.", user, **kw)
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    raw = m.group(1) if m else text
    start = min((i for i in (raw.find("{"), raw.find("[")) if i >= 0), default=0)
    return json.loads(raw[start:])
