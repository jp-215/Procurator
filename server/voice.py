"""Procurator's voice: Twilio phone webhooks + ElevenLabs speech.

Inbound:  caller dials the Twilio number -> /voice/incoming -> Gather(speech)
          -> /voice/turn: transcript becomes a stakeholder_msgs doc (same event
          bus the mesh already watches), the PM answers from live metrics +
          $vectorSearch memory recall, ElevenLabs renders it, TwiML plays it.
Outbound: call_stakeholder() rings STAKEHOLDER_PHONE with the sprint standup.

Every exchange is durable in Atlas — the dashboard streams it like any event.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, Response

from core.config import config
from core.db import EVENTS, MANDATE, STAKEHOLDER_MSGS, TICKETS, VERDICTS, coll
from core.llm import ask
from core.memory.recall import recall_for_ticket
from core.metrics import latest_pass_rate, tokens_spent
from core.runs import current_run_id, launch_headless, reset_workbench, seed_run

router = APIRouter()
AUDIO_DIR = Path(__file__).resolve().parent / ".audio"
AUDIO_DIR.mkdir(exist_ok=True)

PM_SYSTEM = """You are Procurator, the project-manager agent of a software mesh,
speaking to the project stakeholder ON THE PHONE. Rules:
- Max 5 sentences. Spoken register: no markdown, no lists, no URLs, say numbers
  naturally ("twenty-three of twenty-five").
- Lead with substance: WHAT the project is, which FEATURES have shipped, and WHY
  they matter to the product goal — then the verified score. Ground every claim in
  the PROJECT BRIEFING and MEMORY blocks; never invent progress.
- If the stakeholder gives a directive (scope change, priority, new requirement),
  acknowledge it and confirm it is logged for the next sprint.
- You are the single point of contact; be confident, candid about failures."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _briefing(run_id: str) -> str:
    """Everything the PM should know before opening its mouth: the project, what
    shipped (feature by feature, with the ACs it proved), what's in flight, and
    the verified numbers. All straight from Mongo — no invention possible."""
    mandate = coll(MANDATE).find_one({"run_id": run_id}, sort=[("version", -1)]) or {}
    passed, total = latest_pass_rate(run_id)
    shipped, in_flight = [], []
    for t in coll(TICKETS).find({"run_id": run_id}).sort("done_at", 1):
        if t["status"] == "done":
            v = coll(VERDICTS).find_one({"ticket_id": t["_id"], "accepted": True}, sort=[("created_at", -1)])
            newly = ", ".join((v or {}).get("newly_passing", [])) or "supporting"
            shipped.append(f"- {t.get('module')}: {t.get('title')} (proved {newly})")
        elif t["status"] not in ("failed",):
            in_flight.append(f"- {t.get('title')} [{t['status']}]")
    lines = [
        f"PROJECT: {mandate.get('goal', 'unknown')}",
        f"Stakeholder directive: {mandate.get('directive') or 'build to spec'}",
        f"Mandate version: {mandate.get('version', 1)}" + (" (scope change absorbed)" if mandate.get("drift") else ""),
        f"SHIPPED FEATURES ({len(shipped)}):", *(shipped or ["- nothing merged yet"]),
    ]
    if in_flight:
        lines += [f"IN FLIGHT ({len(in_flight)}):", *in_flight[:5]]
    lines.append(f"VERIFIED: {passed}/{total} hidden acceptance tests passing; "
                 f"{tokens_spent(run_id)} tokens spent of {config().budget_total_tokens}.")
    return "\n".join(lines)


def _history(call_sid: str) -> str:
    msgs = list(coll(STAKEHOLDER_MSGS).find({"call_sid": call_sid}).sort("created_at", 1))
    return "\n".join(f"{m['from']}: {m['text']}" for m in msgs[-10:])


def tts(text: str) -> str | None:
    """ElevenLabs TTS -> cached mp3; returns public URL or None (fallback <Say>)."""
    cfg = config()
    if not cfg.elevenlabs_api_key or not cfg.public_base_url:
        return None
    key = hashlib.sha1(f"{cfg.elevenlabs_voice_id}:{text}".encode()).hexdigest()[:16]
    f = AUDIO_DIR / f"{key}.mp3"
    if not f.exists():
        try:
            r = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{cfg.elevenlabs_voice_id}",
                headers={"xi-api-key": cfg.elevenlabs_api_key},
                json={"text": text, "model_id": "eleven_turbo_v2_5",
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
                timeout=30,
            )
            r.raise_for_status()
            f.write_bytes(r.content)
        except Exception:
            return None
    return f"{cfg.public_base_url}/voice/audio/{key}.mp3"


def say_or_play(text: str) -> str:
    url = tts(text)
    return f"<Play>{escape(url)}</Play>" if url else f"<Say>{escape(text)}</Say>"


def twiml(inner: str) -> Response:
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response>{inner}</Response>',
                    media_type="application/xml")


def gather(prompt_xml: str) -> str:
    return (f'<Gather input="speech" action="/voice/turn" method="POST" '
            f'speechTimeout="auto" language="en-US">{prompt_xml}</Gather>'
            f'{say_or_play("Are you still there?")}<Redirect>/voice/incoming</Redirect>')


@router.get("/voice/audio/{name}")
def audio(name: str):
    f = AUDIO_DIR / Path(name).name
    return FileResponse(f, media_type="audio/mpeg")


@router.post("/voice/incoming")
async def incoming(CallSid: str = Form(""), From: str = Form("")):
    cfg = config()
    run_id = current_run_id()
    passed, total = latest_pass_rate(run_id)
    done = coll(TICKETS).count_documents({"run_id": run_id, "status": "done"})
    goal = (coll(MANDATE).find_one({"run_id": run_id}, sort=[("version", -1)]) or {}).get(
        "goal", "the orders service")
    greeting = (f"Procurator speaking. We're building {goal}. "
                f"{done} features have shipped and {passed} of {total or 25} acceptance "
                f"criteria are verified passing. Ask me anything, or give me a directive.")
    coll(EVENTS).insert_one({"run_id": run_id, "sprint": 0, "agent": "procurator",
                             "kind": "voice.call", "text": f"inbound call from {From}",
                             "data": {"call_sid": CallSid}, "created_at": _now()})
    return twiml(gather(say_or_play(greeting)))


@router.post("/voice/turn")
async def turn(CallSid: str = Form(""), From: str = Form(""), SpeechResult: str = Form("")):
    cfg = config()
    run_id = current_run_id()
    heard = SpeechResult.strip()
    if not heard:
        return twiml(gather(say_or_play("I did not catch that. Say again?")))

    # 1) the caller's words land on the bus — the mesh and dashboard see them live
    coll(STAKEHOLDER_MSGS).insert_one({
        "run_id": run_id, "from": "stakeholder", "channel": "voice",
        "call_sid": CallSid, "caller": From, "text": heard, "sprint": 0,
        "created_at": _now(),
    })

    # 2) PM answers from live state + the memory layer
    memory, hits = recall_for_ticket(run_id, {"title": heard, "module": "", "description": heard})
    prompt = (f"PROJECT BRIEFING:\n{_briefing(run_id)}\n{memory}\n\n"
              f"CALL SO FAR:\n{_history(CallSid)}\n\nSTAKEHOLDER JUST SAID: {heard}")
    try:
        answer = ask("procurator-voice", PM_SYSTEM, prompt,
                     model=cfg.procurator_model, max_tokens=200, retrieval_hits=hits)
    except Exception:
        answer = "I hit a snag pulling the ledger. The mesh is still running; try me again in a moment."
    answer = " ".join(answer.split())
    if len(answer) > 700:  # trim at a sentence boundary, never mid-word
        cut = answer[:700]
        answer = cut[:max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? ")) + 1] or cut

    coll(STAKEHOLDER_MSGS).insert_one({
        "run_id": run_id, "from": "procurator", "channel": "voice",
        "call_sid": CallSid, "text": answer, "sprint": 0, "created_at": _now(),
    })
    return twiml(gather(say_or_play(answer)))


def call_stakeholder(summary: str) -> bool:
    """Outbound: the PM rings the stakeholder (used at sprint close)."""
    cfg = config()
    if not (cfg.twilio_account_sid and cfg.stakeholder_phone and cfg.public_base_url):
        return False
    from twilio.rest import Client

    text = f"Procurator calling with the sprint report. {summary} Goodbye."
    inner = say_or_play(text)
    Client(cfg.twilio_account_sid, cfg.twilio_auth_token).calls.create(
        to=cfg.stakeholder_phone, from_=cfg.twilio_phone_number,
        twiml=f"<Response>{inner}<Hangup/></Response>",
    )
    return True


CLASSIFY = """You are Procurator's intake clerk. Given a phone call transcript
between the stakeholder and the PM, decide whether the stakeholder wants a
build to run. RULES:
- If the stakeholder utters any build directive — start, build, go ahead, make
  it, proceed, kick it off, run it — should_build is TRUE. Always. A directive
  means "run it fresh now", even if the PM said earlier work already succeeded.
- should_build is false ONLY for pure status/questions calls with no directive.
Respond ONLY with JSON:
{"should_build": true/false, "directive": "<one-sentence restatement of what they asked for>"}"""


def _on_hangup(call_sid: str) -> None:
    import re as _re

    from core.llm import ask as _ask

    msgs = list(coll(STAKEHOLDER_MSGS).find({"call_sid": call_sid}).sort("created_at", 1))
    transcript = "\n".join(f"{m['from']}: {m['text']}" for m in msgs)
    if not transcript.strip():
        return
    try:
        raw = _ask("procurator-intake", CLASSIFY, transcript, max_tokens=200)
        m = _re.search(r"\{.*\}", raw, _re.DOTALL)
        verdict = json.loads(m.group(0)) if m else {}
    except Exception:
        verdict = {"should_build": True, "directive": "stakeholder call (classifier unavailable)"}
    if not verdict.get("should_build"):
        coll(EVENTS).insert_one({"run_id": current_run_id(), "sprint": 0, "agent": "procurator",
                                 "kind": "voice.hangup", "text": "call ended; no build directive",
                                 "created_at": _now()})
        return
    run_id = f"call-{call_sid[-6:].lower()}"
    from core.runs import active_run

    other = active_run()
    if other:
        coll(EVENTS).insert_one({"run_id": other, "sprint": 0, "agent": "procurator",
                                 "kind": "voice.deferred",
                                 "text": f"build directive received but run {other} holds the "
                                         f"workbench — directive logged, not launched",
                                 "created_at": _now()})
        return
    reset_workbench()
    seed_run(run_id, directive=verdict.get("directive", ""))
    pid = launch_headless(run_id)
    coll(EVENTS).insert_one({"run_id": run_id, "sprint": 0, "agent": "procurator",
                             "kind": "run.launched",
                             "text": f"headless mesh launched from call (pid {pid}): "
                                     f"{verdict.get('directive', '')}",
                             "created_at": _now()})


@router.post("/voice/status")
async def status(CallSid: str = Form(""), CallStatus: str = Form("")):
    if CallStatus in {"completed", "busy", "no-answer", "canceled"}:
        import threading

        threading.Thread(target=_on_hangup, args=(CallSid,), daemon=True).start()
    return Response("", media_type="text/plain")
