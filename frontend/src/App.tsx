import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ask, upload } from './api'
import { useAuth } from './auth'
import { getChat, newChatId, removeChat, saveChat, subscribeChats, type Chat, type StoredMsg } from './history'

const Answer = lazy(() => import('./Answer'))

const CHAT_KEY = 'pagehound-chat:'
const MAX_LOCAL_CHATS = 20

type Local = { uid: string | null; chatLabel: string; msgs: StoredMsg[]; docIds: string[]; attached: { name: string; id?: string; info?: string } | null; updatedAt: number }

function readLocal(id: string): Local | null {
  try {
    const raw = localStorage.getItem(CHAT_KEY + id)
    return raw ? (JSON.parse(raw) as Local) : null
  } catch {
    return null
  }
}

function writeLocal(id: string, value: Local) {
  try {
    localStorage.setItem(CHAT_KEY + id, JSON.stringify(value))
    const keys = Object.keys(localStorage).filter((key) => key.startsWith(CHAT_KEY))
    if (keys.length > MAX_LOCAL_CHATS) {
      const dated = keys.map((key) => [key, (JSON.parse(localStorage.getItem(key) ?? '{}') as Local).updatedAt ?? 0] as const)
      dated.sort((x, y) => x[1] - y[1]).slice(0, keys.length - MAX_LOCAL_CHATS).forEach(([key]) => localStorage.removeItem(key))
    }
  } catch {
    return
  }
}

const chatIdFromPath = () => /^\/c\/([\w-]+)\/?$/.exec(window.location.pathname)?.[1] ?? null
const newLocalId = () => (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '').slice(0, 20) : Math.random().toString(36).slice(2, 12) + Date.now().toString(36))

function go(path: string, replace = false) {
  if (window.location.pathname === path) return
  if (replace) window.history.replaceState({}, '', path)
  else window.history.pushState({}, '', path)
}

type Msg = StoredMsg

const Chevron = () => (
  <svg className="glow-arrow" aria-hidden="true" fill="currentColor" viewBox="0 0 20 20" width="22" height="22">
    <path fillRule="evenodd" clipRule="evenodd" d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L11.94 10 8.22 6.28a.75.75 0 0 1 0-1.06Z" />
  </svg>
)

const GoogleIcon = () => (
  <svg aria-hidden="true" viewBox="0 0 48 48" width="20" height="20">
    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
  </svg>
)

const STAGES: [number, string][] = [
  [0, 'Searching your document'],
  [2500, 'Reading the relevant parts'],
  [6000, 'Writing the answer'],
  [15000, 'Still working, long answers take a little longer'],
  [30000, 'Waking up the server, the first question after a break can take a minute'],
]

function Thinking() {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const start = Date.now()
    const timer = window.setInterval(() => setElapsed(Date.now() - start), 500)
    return () => window.clearInterval(timer)
  }, [])
  const stage = STAGES.filter(([at]) => elapsed >= at).pop()?.[1] ?? STAGES[0][1]
  return (
    <div className="thinking" role="status" aria-live="polite">
      <div className="thinking-row">
        <span className="shimmer">Thinking</span>
        <span className="dots" aria-hidden="true"><i /><i /><i /></span>
      </div>
      <p key={stage} className="thinking-stage">{stage}</p>
    </div>
  )
}

function GlowButton({ children, onClick, icon, className = '' }: { children: React.ReactNode; onClick: () => void; icon?: React.ReactNode; className?: string }) {
  return (
    <div className={`glow-group ${className}`}>
      <button className="glow" onClick={onClick}>
        <span className="glow-ring" />
        <span className="glow-in">
          <span className="glow-row">
            {icon}
            <span className="glow-label">{children}</span>
            <Chevron />
          </span>
        </span>
      </button>
    </div>
  )
}
type Attached = { name: string; loading: boolean; id?: string; info?: string; sent?: boolean; prev?: Attached | null }

const GUEST_MAX_MB = 10
const ACCEPT = '.pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.csv,.tsv,.xlsx,.docx,.pptx,.txt,.md'
const isPdf = (file: File) => file.name.toLowerCase().endsWith('.pdf')
const messageOf = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong.')

const BLOCK_AT = 60

const stripCitations = (text: string) =>
  text
    .replace(/\s*\[[^\]\n]*\b(?:pages?|slides?|rows?|part|image|summary)\b[^\]\n]*\]/gi, '')
    .replace(/\n{3,}/g, '\n\n')

const normalizeMath = (text: string) =>
  text
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `\n\n$$\n${m}\n$$\n\n`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => `$${m}$`)
    .replace(/\$\$[\s\S]+?\$\$|(?<!\\)\$([^$\n]+)\$/g, (match, inline) =>
      inline === undefined
        ? `\n\n$$\n${match.slice(2, -2).trim()}\n$$\n\n`
        : inline.includes('\\begin{') || inline.length > BLOCK_AT
          ? `\n\n$$\n${inline}\n$$\n\n`
          : match,
    )
    .replace(/\\sqrt\{/g, '\\sqrt{\\vphantom{\\Big|}')

function greeting(name?: string) {
  const hour = new Date().getHours()
  const part = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  return name ? `${part}, ${name.split(' ')[0]}` : part
}

const clean = (m: Msg): Msg => ({
  role: m.role,
  text: m.text,
  ...(m.labels?.length ? { labels: m.labels } : {}),
  ...(m.file ? { file: m.file } : {}),
})

const DocIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5M9 13h6M9 17h6" />
  </svg>
)

const ArrowUp = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 19V5M5 12l7-7 7 7" />
  </svg>
)

export default function App({ onContribute }: { onContribute: () => void }) {
  const { user, ready: authReady, signIn, signOut, getToken } = useAuth()
  const [intro, setIntro] = useState(() => !sessionStorage.getItem('intro-seen'))
  const brandRef = useRef<HTMLHeadingElement>(null)
  const [reveal, setReveal] = useState(() => !!sessionStorage.getItem('intro-seen'))
  const [panel, setPanel] = useState(false)
  const [gate, setGate] = useState(false)
  const [gateError, setGateError] = useState('')
  const [pending, setPending] = useState<File | null>(null)
  const [attached, setAttached] = useState<Attached | null>(null)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [chats, setChats] = useState<Chat[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [chatLabel, setChatLabel] = useState('')
  const [text, setText] = useState('')
  const [thinking, setThinking] = useState(false)
  const [error, setError] = useState('')
  const picker = useRef<HTMLInputElement>(null)
  const area = useRef<HTMLTextAreaElement>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const session = useRef(0)
  const uploadSeq = useRef(0)
  const chatDocs = useRef<string[]>([])
  const chatId = useRef<string | null>(null)
  const [hydrated, setHydrated] = useState(false)
  const guestChat = useRef(false)
  const lastUid = useRef<string | null>(null)

  const ready = !!attached?.id && !attached.loading
  const hasChat = msgs.length > 0
  const topLabel = hasChat ? chatLabel || attached?.name || '' : attached?.name ?? ''

  function selectChat(id: string | null) {
    chatId.current = id
    setActiveId(id)
  }

  async function resume(all: Msg[], file: Attached | null) {
    const last = all[all.length - 1]
    if (!last || last.role !== 'user' || chatDocs.current.length === 0) return
    const mine = session.current
    const earlier = all.slice(0, -1)
    const history = earlier.slice(-6).map((m) => ({ role: m.role, text: m.text.slice(0, 1500) }))
    setThinking(true)
    try {
      const result = await ask(chatDocs.current, last.text, history, await getToken())
      if (mine !== session.current) return
      const done: Msg[] = [...all, { role: 'assistant', text: result.answer }]
      setMsgs(done)
      void persist(done, file)
    } catch (e) {
      if (mine !== session.current) return
      setError(messageOf(e))
      setMsgs(earlier)
      setText(last.text)
    } finally {
      if (mine === session.current) setThinking(false)
    }
  }

  async function loadFromUrl() {
    const id = chatIdFromPath()
    if (!id) {
      if (chatId.current) resetChat(false)
      return
    }
    if (id === chatId.current) return
    const local = readLocal(id)
    if (local && local.uid === (user?.uid ?? null)) {
      session.current++
      chatDocs.current = local.docIds
      guestChat.current = local.uid === null
      selectChat(id)
      setChatLabel(local.chatLabel)
      setMsgs(local.msgs)
      const restored = local.attached ? { ...local.attached, loading: false, sent: true } : null
      setAttached(restored)
      setError('')
      void resume(local.msgs, restored)
      return
    }
    if (user) {
      try {
        const remote = await getChat(user.uid, id)
        if (remote) {
          guestChat.current = false
          openChat(remote, false)
          return
        }
      } catch (e) {
        console.warn('Could not load this chat', e)
      }
    }
    resetChat(false)
    go('/', true)
  }

  useEffect(() => {
    if (!authReady || hydrated) return
    void loadFromUrl().finally(() => setHydrated(true))
  }, [authReady])

  useEffect(() => {
    if (!hydrated) return
    const onPop = () => void loadFromUrl()
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [hydrated, user?.uid])

  useEffect(() => {
    if (!hydrated) return
    const previous = lastUid.current
    lastUid.current = user?.uid ?? null
    if (previous && previous !== (user?.uid ?? null)) resetChat()
    if (!previous && user && guestChat.current && msgs.length > 0) {
      guestChat.current = false
      void persist(msgs, attached)
    }
  }, [hydrated, user?.uid])

  useEffect(() => {
    if (!hydrated || !chatId.current || msgs.length === 0 || attached?.loading) return
    const ids = [...new Set([...chatDocs.current, ...(attached?.id ? [attached.id] : [])])]
    writeLocal(chatId.current, {
      uid: user?.uid ?? null,
      chatLabel,
      msgs,
      docIds: ids,
      attached: attached ? { name: attached.name, id: attached.id, info: attached.info } : null,
      updatedAt: Date.now(),
    })
  }, [hydrated, msgs, chatLabel, attached, activeId, user?.uid])

  useLayoutEffect(() => {
    const box = brandRef.current
    const word = box?.querySelector<HTMLElement>('.brand-word')
    if (!box || !word) return
    const measure = () => {
      const size = parseFloat(getComputedStyle(box).fontSize)
      if (size) box.style.setProperty('--tw', `${word.offsetWidth / size}em`)
    }
    measure()
    void document.fonts?.ready.then(measure)
  }, [])

  useEffect(() => {
    if (!intro) return
    const show = setTimeout(() => setReveal(true), 800)
    const done = setTimeout(() => {
      sessionStorage.setItem('intro-seen', '1')
      setIntro(false)
    }, 2400)
    return () => {
      clearTimeout(show)
      clearTimeout(done)
    }
  }, [intro])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [msgs, thinking])

  useEffect(() => {
    const box = area.current
    if (!box) return
    box.style.height = 'auto'
    box.style.height = `${Math.min(box.scrollHeight, 160)}px`
  }, [text])

  useEffect(() => {
    if (!user) {
      setChats([])
      return
    }
    return subscribeChats(user.uid, setChats)
  }, [user?.uid])

  useEffect(() => {
    if (user && pending) {
      const file = pending
      setPending(null)
      setGate(false)
      void handleFile(file)
    }
  }, [user])

  async function handleFile(file: File) {
    setError('')
    if (!user && !isPdf(file)) {
      setPending(file)
      setGateError('')
      setGate(true)
      return
    }
    if (!user && file.size > GUEST_MAX_MB * 1024 * 1024) {
      setError(`Guests can upload files up to ${GUEST_MAX_MB} MB.`)
      return
    }
    const chat = session.current
    const mine = ++uploadSeq.current
    const base = attached && !attached.loading ? attached : attached?.prev ?? null
    const before = base ? { ...base, prev: null } : null
    setAttached({ name: file.name, loading: true, prev: before })
    try {
      const result = await upload(file, await getToken())
      if (chat !== session.current || mine !== uploadSeq.current) return
      const info = [
        result.ocr_pages.length ? `${result.ocr_pages.length} scanned page(s) read with OCR` : '',
        result.truncated
          ? user
            ? 'Only part of this large file was indexed'
            : `Only the first ${result.pages_processed} pages were indexed. Sign in for more.`
          : '',
      ].filter(Boolean).join(' · ')
      setAttached({ name: result.filename, loading: false, id: result.doc_id, info, sent: false, prev: before })
    } catch (e) {
      if (chat !== session.current || mine !== uploadSeq.current) return
      setAttached(before)
      setError(messageOf(e))
    }
  }

  async function persist(all: Msg[], file?: Attached | null) {
    if (!user) return
    let id = chatId.current
    if (!id) {
      id = newChatId(user.uid)
      selectChat(id)
    }
    const first = all.find((m) => m.role === 'user')?.text ?? 'New chat'
    const files = [...new Set(all.flatMap((m) => (m.file ? [m.file] : [])))]
    try {
      await saveChat(user.uid, {
        id,
        title: first.slice(0, 60),
        fileName: files[0] ?? file?.name ?? '',
        files,
        docId: file?.id,
        messages: all.map(clean),
      })
    } catch (e) {
      console.warn('Could not save this chat', e)
    }
  }

  async function send() {
    const question = text.trim()
    if (!question || !attached?.id || attached.loading || thinking) return
    const mine = session.current
    const history = msgs.slice(-6).map((m) => ({ role: m.role, text: m.text.slice(0, 1500) }))
    const file = attached.sent ? undefined : attached.name
    if (!chatLabel) setChatLabel(attached.name)
    if (!chatId.current) {
      const id = user ? newChatId(user.uid) : newLocalId()
      guestChat.current = !user
      selectChat(id)
      go(`/c/${id}`)
    }
    const base: Msg[] = [...msgs, { role: 'user', text: question, ...(file ? { file } : {}) }]
    setText('')
    setError('')
    setMsgs(base)
    setAttached((current) => (current ? { ...current, sent: true, prev: null } : current))
    setThinking(true)
    try {
      const ids = [...new Set([...chatDocs.current, attached.id])]
      chatDocs.current = ids
      const result = await ask(ids, question, history, await getToken())
      if (mine !== session.current) return
      const all: Msg[] = [...base, { role: 'assistant', text: result.answer }]
      setMsgs(all)
      void persist(all, attached)
    } catch (e) {
      if (mine !== session.current) return
      setError(messageOf(e))
      setMsgs(msgs)
      setText(question)
      if (file) setAttached((current) => (current ? { ...current, sent: false } : current))
    } finally {
      if (mine === session.current) setThinking(false)
    }
  }

  function resetChat(push = true) {
    session.current++
    chatDocs.current = []
    selectChat(null)
    setChatLabel('')
    setAttached(null)
    setMsgs([])
    setText('')
    setError('')
    setThinking(false)
    if (push) go('/')
  }

  function newChat() {
    resetChat()
    setPanel(false)
  }

  function openChat(chat: Chat, push = true) {
    session.current++
    const local = readLocal(chat.id)
    chatDocs.current = local && local.uid === (user?.uid ?? null) ? local.docIds : chat.docId ? [chat.docId] : []
    selectChat(chat.id)
    setChatLabel(chat.files[0] ?? chat.fileName)
    setMsgs(chat.messages)
    setAttached({ name: chat.files.at(-1) ?? chat.fileName, loading: false, id: chat.docId, sent: true })
    setText('')
    setError('')
    setThinking(false)
    setPanel(false)
    if (push) go(`/c/${chat.id}`)
  }

  async function deleteChat(chat: Chat) {
    if (!user || !window.confirm('Delete this chat?')) return
    await removeChat(user.uid, chat.id)
    if (chatId.current === chat.id) resetChat()
  }

  async function doSignOut() {
    await signOut()
    resetChat()
    setPanel(false)
  }

  async function startSignIn() {
    setGateError('')
    try {
      await signIn()
      setGate(false)
    } catch (e) {
      setGateError(messageOf(e))
    }
  }

  function closeGate() {
    setGate(false)
    setPending(null)
  }

  return (
    <div className={intro ? 'app intro' : 'app'}>
      <div className="aurora" aria-hidden="true" />
      <h1 ref={brandRef} className={reveal ? 'brand reveal' : 'brand'}>
        <img className="brand-logo" src="/logo.png" alt="" />
        <span className="brand-text"><span className="brand-word">PAGEHOUND</span></span>
      </h1>

      <header className="bar">
        <div className="bar-left">
          <button className="icon" aria-label="History" onClick={() => setPanel(true)}>☰</button>
          {topLabel && <span className="filename" title={topLabel}>{topLabel}</span>}
        </div>
        <div className="bar-right">
          {authReady && !user && (
            <GlowButton className="small" onClick={() => { setGateError(''); setGate(true) }}>Sign in</GlowButton>
          )}
        </div>
      </header>

      <main className="main">
        {!hasChat ? (
          <div className="hello">
            <img className="hello-logo" src="/logo.png" alt="" />
            <h2>{greeting(user?.name)}</h2>
          </div>
        ) : (
          <div className="chat">
            {msgs.map((m, i) => (
              <div key={i} className={`turn ${m.role}`}>
                {m.file && (
                  <div className="chip">
                    <span className="tile"><DocIcon /></span>
                    <span className="chip-name">{m.file}</span>
                  </div>
                )}
                <div className={`msg ${m.role}`}>
                  {m.role === 'assistant' ? (
                    <div className="md">
                      <Suspense fallback={<p>{stripCitations(m.text)}</p>}>
                        <Answer text={normalizeMath(stripCitations(m.text))} />
                      </Suspense>
                    </div>
                  ) : (
                    <p>{m.text}</p>
                  )}
                </div>
              </div>
            ))}
            {thinking && <div className="turn assistant"><Thinking /></div>}
            <div ref={bottom} />
          </div>
        )}

        {error && <p className="error">{error}</p>}

        <div className="composer">
          <div className="box">
            {attached?.name && !attached.sent && (
              <div className="chip" title={attached.info}>
                <span className="tile">{attached.loading ? <span className="spin" /> : <DocIcon />}</span>
                <span className="chip-name">{attached.name}</span>
                {ready && (
                  <button className="chip-x" aria-label="Remove file" onClick={() => setAttached(attached.prev ?? null)}>×</button>
                )}
              </div>
            )}
            <textarea
              ref={area}
              rows={1}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void send()
                }
              }}
              placeholder={attached && !attached.sent ? 'Ask about this file…' : hasChat ? 'Ask a follow-up…' : 'Click + to upload a file'}
            />
            <div className="row">
              <button className="icon" aria-label="Upload a file" title="Upload a file (guests: PDF up to 10 MB)" onClick={() => picker.current?.click()}>+</button>
              <button className="send" aria-label="Send" onClick={() => void send()} disabled={!ready || thinking || !text.trim()}>
                <ArrowUp />
              </button>
            </div>
          </div>
          <p className="notice">
            Files are deleted within 2 hours. Answers use Google's free Gemini tier, where Google may review content, so avoid uploading sensitive personal documents.
          </p>
        </div>
        <input
          ref={picker}
          type="file"
          accept={ACCEPT}
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) void handleFile(file)
          }}
        />
      </main>

      <footer className="foot">
        <span>Made by Vigesh</span>
        <div>
          <a
            href="/contribute"
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
              e.preventDefault()
              onContribute()
            }}
          >
            Contribute
          </a>
          <button className="icon" aria-label="Back to top" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>↑</button>
        </div>
      </footer>

      {panel && <div className="scrim" onClick={() => setPanel(false)} />}
      <aside className={panel ? 'panel open' : 'panel'}>
        <div className="panel-head">
          <strong>History</strong>
          <button className="icon" aria-label="Close history" onClick={() => setPanel(false)}>×</button>
        </div>
        <button className="ghost new" onClick={newChat}>+ New chat</button>
        {user ? (
          <div className="history">
            {chats.length === 0 ? (
              <p className="hint">No saved chats yet.</p>
            ) : (
              chats.map((chat) => (
                <div key={chat.id} className={chat.id === activeId ? 'item active' : 'item'}>
                  <button className="item-main" onClick={() => openChat(chat)}>
                    <span className="item-title">{chat.title}</span>
                    {chat.fileName && (
                      <span className="item-file">
                        {chat.files.length > 1 ? `${chat.files[0]} +${chat.files.length - 1} more` : chat.files[0] ?? chat.fileName}
                      </span>
                    )}
                  </button>
                  <button className="item-x" aria-label="Delete chat" onClick={() => void deleteChat(chat)}>×</button>
                </div>
              ))
            )}
          </div>
        ) : (
          <>
            <p className="hint">Sign in to save and view your chats.</p>
            <GlowButton className="small" onClick={() => { setPanel(false); setGate(true) }}>Sign in</GlowButton>
          </>
        )}
        {user && <button className="ghost signout" onClick={() => void doSignOut()}>Sign out</button>}
      </aside>

      {gate && (
        <div className="scrim center" onClick={closeGate}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <img className="modal-logo" src="/logo.png" alt="" />
            <h2>{pending ? 'Sign in to unlock this file type' : 'Sign in to Pagehound'}</h2>
            <p>Signed-in users can upload photos, CSV, Excel, Word, PowerPoint and text files, and keep their chat history.</p>
            <GlowButton icon={<GoogleIcon />} onClick={() => void startSignIn()}>Continue with Google</GlowButton>
            {gateError && <p className="error">{gateError}</p>}
            <button className="ghost" onClick={closeGate}>Not now</button>
          </div>
        </div>
      )}
    </div>
  )
}
