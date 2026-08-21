"""Pins the sidecar wire contract without Node.

The stub binds loopback on port 0 in a daemon thread: no external network, no
provider SDK, nothing to install. This is the only place the HTTP contract in
`sidecar/whatsapp/README.md` is executable, so it is worth a real socket.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from replaygate.channels.baileys import BaileysTransport, SidecarUnavailable

STATE = {"messages": [], "sent": [], "connected": True}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        params = dict(p.split("=", 1) for p in query.split("&") if p)
        if path == "/health":
            return self._json(200, {"status": "ok", "connected": STATE["connected"],
                                    "has_peer": True})
        if path == "/inbound":
            after = int(params.get("after", "0"))
            fresh = STATE["messages"][after:]
            return self._json(200, {"cursor": after + len(fresh), "messages": fresh})
        return self._json(404, {"error": "no such endpoint"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/outbound":
            STATE["sent"].append(payload["text"])
            return self._json(200, {"id": f"OUT-{len(STATE['sent'])}"})
        return self._json(404, {"error": "no such endpoint"})


@pytest.fixture
def sidecar():
    STATE["messages"] = []
    STATE["sent"] = []
    STATE["connected"] = True
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()


def test_poll_maps_the_wire_payload_to_inbound_messages(sidecar):
    STATE["messages"] = [
        {"id": "3EB0A1", "text": "hey there", "sent_at": 1787000000.0},
        {"id": "3EB0A2", "text": "my order ORD-1234", "sent_at": 1787000001.0},
    ]
    transport = BaileysTransport(sidecar)
    got = transport.poll(1.0)
    assert [m.id for m in got] == ["3EB0A1", "3EB0A2"]
    assert got[0].text == "hey there"
    assert got[0].sent_at.tzinfo is not None
    assert got[1].sent_at > got[0].sent_at


def test_the_cursor_advances_so_a_message_is_never_delivered_twice(sidecar):
    STATE["messages"] = [{"id": "3EB0A1", "text": "one", "sent_at": 1787000000.0}]
    transport = BaileysTransport(sidecar)
    assert len(transport.poll(1.0)) == 1
    assert transport.poll(1.0) == []
    STATE["messages"].append({"id": "3EB0A2", "text": "two", "sent_at": 1787000002.0})
    assert [m.id for m in transport.poll(1.0)] == ["3EB0A2"]


def test_send_posts_the_text_and_returns_the_channel_id(sidecar):
    transport = BaileysTransport(sidecar)
    assert transport.send("hello back") == "OUT-1"
    assert STATE["sent"] == ["hello back"]


def test_now_is_timezone_aware_wall_clock(sidecar):
    assert BaileysTransport(sidecar).now().tzinfo is not None


def test_an_unreachable_sidecar_raises_sidecar_unavailable():
    # Port 1 on loopback: nothing listens there, and the connection is refused fast.
    transport = BaileysTransport("http://127.0.0.1:1")
    with pytest.raises(SidecarUnavailable) as excinfo:
        transport.health()
    assert "127.0.0.1:1" in str(excinfo.value)
