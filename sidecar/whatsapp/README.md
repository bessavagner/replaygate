# ReplayGate WhatsApp sidecar

A throwaway transport between a WhatsApp number and ReplayGate. **Showcase only**:
a test number, no real users, no advertising, no customer service. Baileys is an
unofficial client — a number can be banned for using it. Never point this at a
number you care about: enforcement is at the *account* level, so the ban takes the
number itself, not just the linked device, and it is usually permanent.

## Run it

```bash
cd sidecar/whatsapp
npm install
REPLAYGATE_ALLOWED_NUMBERS='+55 85 91234-5678' npm start
```

It prints a QR code. On the throwaway phone: **WhatsApp → Settings → Linked devices →
Link a device**, and scan. The session persists in `./auth/` (git-ignored — those are
device credentials).

Then, from the repo root:

```bash
replaygate record-whatsapp whatsapp_support ./fixtures/whatsapp_support --max-turns 4
```

## Whose messages get recorded

`REPLAYGATE_ALLOWED_NUMBERS` is a comma-separated whitelist of senders. Everything else
is dropped in `messages.upsert` and never reaches Python. Matching is on digits only, so
`+55 85 91234-5678`, `5585912345678`, and a full JID all match the same person. Group JIDs
(`@g.us`) never match a phone number, which drops group chats for free.

**Set it.** `fixtures/` is committed to git: without a whitelist, any stranger who messages
this number lands in a permanent, public artifact. Unset means *record anyone*, and the
sidecar warns loudly at boot when that is the case.

It is not a ban mitigation — see the warning at the top. The number paired to this sidecar
is the one at risk, and no whitelist changes that.

## Why `baileys` is pinned to 6.7.24

Pinned exactly, not caret-ranged: npm's `latest` tag is `7.0.0-rc14`, and a caret range
would drift onto a release candidate.

The version is `6.7.24` (npm's `legacy` tag) rather than the numerically-higher `6.17.16`
because npm publishes an active advisory against the latter — GHSA-qvv5-jq5g-4cgg, message
spoofing, affecting `<=6.7.18 || 6.17.16`. `npm audit` on 6.7.24 reports zero
vulnerabilities. It is the maintained WhiskeySockets line and exposes the same
`makeWASocket` / `DisconnectReason` / `useMultiFileAuthState` surface `server.js` uses.

## Wire contract

Python is always the client. The sidecar never calls out.

| Endpoint | Request | Response |
|---|---|---|
| `GET /health` | — | `{"status":"ok","connected":true,"has_peer":true}` |
| `GET /inbound?after=<int>&timeout_ms=<int>` | long-polls up to `timeout_ms` | `{"cursor":<int>,"messages":[{"id":str,"text":str,"sent_at":<unix seconds>}]}` |
| `POST /outbound` | `{"text": str}` | `{"id": str}` |

`sent_at` is Unix seconds so neither side has to agree on a datetime format.
`after` is the cursor from the previous poll; a message is never delivered twice.

**There is no sender field, deliberately.** The peer's JID stays in this process.
ReplayGate learns what was said and when, never who by. `tests/channels/test_baileys_transport.py`
pins this contract from the Python side without Node.

## Scope

Text messages only. Media, reactions, receipts, and group chats are dropped in
`messages.upsert` — out of scope for a showcase transport.

## Common failures

| Symptom | Cause |
|---|---|
| `logged out — delete ./auth and pair again` | the phone unlinked the device |
| `409 no peer yet` | the agent tried to reply before any inbound message arrived |
| QR never appears | a stale `./auth/` — delete it and restart |
| `unable to determine transport target for "pino-pretty"` | `npm i -D pino-pretty`, or drop the `transport` option in `server.js` |
