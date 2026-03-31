import { create } from 'zustand'

type MessageRole = 'user' | 'assistant'

interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp: number
  metadata?: Record<string, unknown>
}

interface WebSocketStore {
  ws: WebSocket | null
  connected: boolean
  sessionId: string
  messages: Message[]
  connect: () => void
  disconnect: () => void
  sendMessage: (content: string) => void
  addMessage: (message: Message) => void
  replaceMessages: (messages: Message[]) => void
}

const STORAGE_KEY = 'roboclaw.web.chat_id'

function createSessionId(): string {
  return `web-${Math.random().toString(36).slice(2, 10)}`
}

function getOrCreateSessionId(): string {
  const existing = window.localStorage.getItem(STORAGE_KEY)
  if (existing) {
    return existing
  }
  const created = createSessionId()
  window.localStorage.setItem(STORAGE_KEY, created)
  return created
}

function persistSessionId(sessionId: string): void {
  window.localStorage.setItem(STORAGE_KEY, sessionId)
}

function normalizeTimestamp(value: unknown): number {
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Date.parse(value)
    if (!Number.isNaN(parsed)) {
      return parsed
    }
  }
  return Date.now()
}

function resolveWebSocketUrl(sessionId: string): string {
  const override = import.meta.env.VITE_WEBSOCKET_URL as string | undefined
  const url = override
    ? new URL(override)
    : new URL('/ws', window.location.href)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.searchParams.set('chat_id', sessionId)
  return url.toString()
}

function normalizeHistoryMessage(message: any): Message {
  return {
    id: String(message.id ?? `${message.role ?? 'assistant'}-${Math.random()}`),
    role: message.role === 'user' ? 'user' : 'assistant',
    content: String(message.content ?? ''),
    timestamp: normalizeTimestamp(message.timestamp),
    metadata: message.metadata ?? {},
  }
}

export const useWebSocket = create<WebSocketStore>((set, get) => ({
  ws: null,
  connected: false,
  sessionId: '',
  messages: [],

  connect: () => {
    const current = get()
    if (current.ws || current.connected) {
      return
    }

    const sessionId = current.sessionId || getOrCreateSessionId()
    const ws = new WebSocket(resolveWebSocketUrl(sessionId))
    set({ ws, connected: false, sessionId })

    ws.onopen = () => {
      if (get().ws !== ws) {
        return
      }
      set({ connected: true, sessionId })
    }

    ws.onmessage = (event) => {
      if (get().ws !== ws) {
        return
      }
      const data = JSON.parse(event.data)

      if (data.type === 'session') {
        const resolvedSessionId = String(data.chat_id || sessionId)
        persistSessionId(resolvedSessionId)
        set({
          sessionId: resolvedSessionId,
          messages: Array.isArray(data.history) ? data.history.map(normalizeHistoryMessage) : [],
        })
        return
      }

      if (data.type === 'message') {
        get().addMessage({
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          role: data.role === 'user' ? 'user' : 'assistant',
          content: String(data.content ?? ''),
          timestamp: normalizeTimestamp(data.timestamp),
          metadata: data.metadata ?? {},
        })
      }
    }

    ws.onclose = () => {
      if (get().ws !== ws) {
        return
      }
      set({ connected: false, ws: null })
      window.setTimeout(() => {
        if (!get().connected && !get().ws) {
          get().connect()
        }
      }, 3000)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  },

  disconnect: () => {
    const { ws } = get()
    set({ ws: null, connected: false })
    if (ws) {
      ws.close()
    }
  },

  sendMessage: (content: string) => {
    const { ws, connected, sessionId } = get()
    if (!connected || !ws) {
      console.error('WebSocket not connected')
      return
    }

    get().addMessage({
      id: `${Date.now()}-user`,
      role: 'user',
      content,
      timestamp: Date.now(),
      metadata: {},
    })

    ws.send(
      JSON.stringify({
        content,
        metadata: {},
        session_id: sessionId,
      }),
    )
  },

  addMessage: (message: Message) => {
    set((state) => ({
      messages: [...state.messages, message],
    }))
  },

  replaceMessages: (messages: Message[]) => {
    set({ messages })
  },
}))
