// ReplayGate WhatsApp sidecar — transport only.
//
// Owns the WhatsApp socket and exposes three endpoints to Python. It never sees
// an agent, an LLM, or a fixture. Two rules it must not break:
//
//   1. The peer's JID stays in this process. ReplayGate learns what was said and
//      when, never who by. Do not add a sender field to /inbound.
//   2. /inbound long-polls. Blocking here rather than in Python is what makes a
//      burst gap measured on the channel's clock.
import express from 'express'
import pino from 'pino'
import qrcode from 'qrcode-terminal'
import makeWASocket, { DisconnectReason, useMultiFileAuthState } from 'baileys'

const PORT = Number(process.env.PORT ?? 8787)
const log = pino({ transport: { target: 'pino-pretty' } , level: process.env.LOG_LEVEL ?? 'info' })

// Only these senders are recorded. `fixtures/` is committed to git, so without a
// whitelist any stranger who messages this number lands in a permanent artifact.
// Digits only, so "+55 85 91234-5678", "5585912345678" and a full JID all match.
// Group JIDs (@g.us) never match a phone number, which drops group chats for free.
const ALLOWED = (process.env.REPLAYGATE_ALLOWED_NUMBERS ?? '')
  .split(',').map((n) => n.replace(/\D/g, '')).filter(Boolean)

function isAllowed(jid) {
  if (!ALLOWED.length) return true      // unset = record anyone; warned about at boot
  const digits = String(jid ?? '').split('@')[0].split(':')[0].replace(/\D/g, '')
  return ALLOWED.includes(digits)
}

const inbound = []          // { id, text, sent_at } — index is the cursor
const waiters = []          // resolve callbacks parked by an empty long-poll
let peerJid = null          // NEVER leaves this process
let connected = false
let sock = null

function push(message) {
  inbound.push(message)
  while (waiters.length) waiters.shift()()
}

async function connect() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth')
  sock = makeWASocket({ auth: state, logger: pino({ level: 'silent' }) })

  sock.ev.on('creds.update', saveCreds)

  sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      log.info('scan this QR with the throwaway number (WhatsApp → Linked devices)')
      qrcode.generate(qr, { small: true })
    }
    if (connection === 'open') {
      connected = true
      log.info('paired and connected')
    }
    if (connection === 'close') {
      connected = false
      const status = lastDisconnect?.error?.output?.statusCode
      if (status === DisconnectReason.loggedOut) {
        log.error('logged out — delete ./auth and pair again')
        return
      }
      log.warn({ status }, 'connection closed, reconnecting')
      connect()
    }
  })

  sock.ev.on('messages.upsert', ({ messages, type }) => {
    if (type !== 'notify') return
    for (const m of messages) {
      if (m.key.fromMe) continue
      const text = m.message?.conversation ?? m.message?.extendedTextMessage?.text
      if (!text) continue          // media, reactions, receipts: out of scope
      if (!isAllowed(m.key.remoteJid)) {
        // Do not log the JID: it is exactly the thing that must not escape.
        log.warn('dropped a message from a sender outside REPLAYGATE_ALLOWED_NUMBERS')
        continue
      }
      peerJid = m.key.remoteJid
      push({ id: m.key.id, text, sent_at: Number(m.messageTimestamp) })
      log.info({ id: m.key.id }, 'inbound')
    }
  })
}

const app = express()
app.use(express.json())

app.get('/health', (_req, res) => {
  res.json({ status: 'ok', connected, has_peer: peerJid !== null })
})

app.get('/inbound', async (req, res) => {
  const after = Number(req.query.after ?? 0)
  const timeoutMs = Number(req.query.timeout_ms ?? 2000)
  if (inbound.length <= after) {
    await new Promise((resolve) => {
      const timer = setTimeout(resolve, timeoutMs)
      waiters.push(() => { clearTimeout(timer); resolve() })
    })
  }
  const messages = inbound.slice(after)
  res.json({ cursor: after + messages.length, messages })
})

app.post('/outbound', async (req, res) => {
  if (!peerJid) return res.status(409).json({ error: 'no peer yet — send an inbound message first' })
  const sent = await sock.sendMessage(peerJid, { text: req.body.text })
  log.info({ id: sent.key.id }, 'outbound')
  res.json({ id: sent.key.id })
})

if (!ALLOWED.length) {
  log.warn(
    'REPLAYGATE_ALLOWED_NUMBERS is unset — every sender will be recorded into the fixture. ' +
    'Set it to your own number before pairing.'
  )
} else {
  log.info(`recording ${ALLOWED.length} whitelisted sender(s)`)
}

await connect()
app.listen(PORT, '127.0.0.1', () => log.info(`sidecar listening on http://127.0.0.1:${PORT}`))
