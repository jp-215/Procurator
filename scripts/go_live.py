"""Sync the voice stack to the current tunnel: detect the cloudflared URL,
write PUBLIC_BASE_URL to .env, and point the Twilio number's webhook at it.

Run AFTER the tunnel is up:  .venv/bin/python scripts/go_live.py
"""
from __future__ import annotations

import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
TUNNEL_LOG = Path("/tmp/procurator-tunnel.log")


def tunnel_url() -> str:
    for _ in range(30):
        if TUNNEL_LOG.exists():
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", TUNNEL_LOG.read_text())
            if m:
                return m.group(0)
        time.sleep(1)
    raise SystemExit(f"no tunnel URL found in {TUNNEL_LOG} — is the tunnel terminal running?")


def main() -> None:
    url = tunnel_url()
    env = ROOT / ".env"
    lines = env.read_text().splitlines()
    found = False
    for i, l in enumerate(lines):
        if l.startswith("PUBLIC_BASE_URL"):
            lines[i] = f'PUBLIC_BASE_URL="{url}"'
            found = True
    if not found:
        lines.append(f'PUBLIC_BASE_URL="{url}"')
    env.write_text("\n".join(lines) + "\n")
    print("PUBLIC_BASE_URL =", url)

    from core.config import Config
    from twilio.rest import Client

    c = Config()
    tw = Client(c.twilio_account_sid, c.twilio_auth_token)
    n = tw.incoming_phone_numbers.list(phone_number=c.twilio_phone_number)[0]
    n.update(voice_url=f"{url}/voice/incoming", voice_method="POST",
             status_callback=f"{url}/voice/status", status_callback_method="POST")
    print(f"Twilio {c.twilio_phone_number} webhook -> {url}/voice/incoming (+status callback)")

    # confirm the public loop answers
    req = urllib.request.Request(f"{url}/voice/incoming", data=b"CallSid=CAgolive", method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode()
    print("public round-trip:", "OK — PM answered" if "<Response>" in body else body[:120])


if __name__ == "__main__":
    main()
