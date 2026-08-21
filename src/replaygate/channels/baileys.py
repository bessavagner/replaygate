"""HTTP client for the Node Baileys sidecar.

Python is a client and never a server: the sidecar owns the WhatsApp socket,
buffers inbound messages, and hands them over by cursor. Long-polling means a
burst gap is waited out *in the sidecar*, on the channel's clock, rather than in
a Python sleep loop.

Uses ``urllib`` from the stdlib on purpose — this is the only networked module in
the package and it does not justify a runtime dependency.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

from replaygate.channels.transport import InboundMessage

DEFAULT_SIDECAR = "http://127.0.0.1:8787"


class SidecarUnavailable(RuntimeError):
    """The sidecar did not answer — not running, wrong port, or not paired yet."""


class BaileysTransport:
    #: Seconds added to a long-poll's own timeout before the socket gives up.
    SLACK_S = 5.0

    def __init__(self, base_url: str = DEFAULT_SIDECAR):
        self._base_url = base_url.rstrip("/")
        self._cursor = 0

    def _request(self, path: str, timeout: float, payload: dict | None = None) -> dict:
        url = f"{self._base_url}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read() or b"{}")
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            raise SidecarUnavailable(f"sidecar at {self._base_url} did not answer: {e}") from None

    def health(self) -> dict:
        return self._request("/health", timeout=self.SLACK_S)

    def poll(self, timeout_s: float) -> list[InboundMessage]:
        payload = self._request(
            f"/inbound?after={self._cursor}&timeout_ms={int(timeout_s * 1000)}",
            timeout=timeout_s + self.SLACK_S,
        )
        self._cursor = payload["cursor"]
        return [
            InboundMessage(
                id=m["id"],
                text=m["text"],
                sent_at=datetime.fromtimestamp(m["sent_at"], tz=timezone.utc),
            )
            for m in payload["messages"]
        ]

    def send(self, text: str) -> str:
        return self._request("/outbound", timeout=self.SLACK_S, payload={"text": text})["id"]

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
