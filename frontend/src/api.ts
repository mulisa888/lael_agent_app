import type {
  AuditItem,
  Conversation,
  GoogleStatus,
  Message,
  NoteItem,
  PendingApproval,
  ReminderItem,
  Settings,
  SystemInfo,
  TaskItem,
} from './types'

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(txt || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  getSettings: () => req<Settings>('/api/settings'),
  updateSettings: (patch: Record<string, unknown>) =>
    req<Settings>('/api/settings', { method: 'PATCH', body: JSON.stringify(patch) }),
  resetSettings: () => req<Settings>('/api/settings/reset', { method: 'POST' }),

  getOllamaModels: () => req<{ online: boolean; models: string[]; error?: string }>('/api/providers/ollama/models'),

  listConversations: () => req<Conversation[]>('/api/conversations'),
  createConversation: (title = 'New Chat') =>
    req<Conversation>('/api/conversations', { method: 'POST', body: JSON.stringify({ title }) }),
  getConversation: (id: string) =>
    req<{ conversation: Conversation; messages: Message[] }>(`/api/conversations/${id}`),
  deleteConversation: (id: string) => req<{ ok: boolean }>(`/api/conversations/${id}`, { method: 'DELETE' }),

  chat: (conversation_id: string | null, message: string) =>
    req<{ conversation_id: string; message: Message; pending_approvals: PendingApproval[] }>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ conversation_id, message }),
    }),

  listTasks: (status = 'all') => req<TaskItem[]>(`/api/tasks?status=${status}`),
  createTask: (payload: Partial<TaskItem>) =>
    req<TaskItem>('/api/tasks', { method: 'POST', body: JSON.stringify(payload) }),
  updateTask: (id: string, payload: Partial<TaskItem>) =>
    req<TaskItem>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteTask: (id: string) => req<{ ok: boolean }>(`/api/tasks/${id}`, { method: 'DELETE' }),

  listNotes: (q = '') => req<NoteItem[]>(`/api/notes?q=${encodeURIComponent(q)}`),
  createNote: (payload: Partial<NoteItem>) =>
    req<NoteItem>('/api/notes', { method: 'POST', body: JSON.stringify(payload) }),
  updateNote: (id: string, payload: Partial<NoteItem>) =>
    req<NoteItem>(`/api/notes/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteNote: (id: string) => req<{ ok: boolean }>(`/api/notes/${id}`, { method: 'DELETE' }),

  listReminders: () => req<ReminderItem[]>('/api/reminders'),
  createReminder: (payload: Partial<ReminderItem>) =>
    req<ReminderItem>('/api/reminders', { method: 'POST', body: JSON.stringify(payload) }),
  deleteReminder: (id: string) => req<{ ok: boolean }>(`/api/reminders/${id}`, { method: 'DELETE' }),
  testNotification: () => req<{ ok: boolean }>('/api/reminders/test-notification', { method: 'POST' }),

  getBriefing: () => req<Record<string, unknown>>('/api/briefing'),

  getKbFiles: () =>
    req<{ folders: string[]; extensions: string[]; files: { path: string; size: number; chunk_count: number; indexed_at: string }[] }>('/api/kb/files'),
  addKbFolder: (folder: string) =>
    req<{ folders: string[]; index_result: Record<string, unknown> }>('/api/kb/folders', {
      method: 'POST',
      body: JSON.stringify({ folder }),
    }),
  removeKbFolder: (folder: string) =>
    req<{ folders: string[]; index_result: Record<string, unknown> }>(
      `/api/kb/folders?folder=${encodeURIComponent(folder)}`,
      { method: 'DELETE' }
    ),
  reindexKb: () => req<Record<string, unknown>>('/api/kb/reindex', { method: 'POST' }),
  searchKb: (q: string) =>
    req<{ query: string; matches: { file_name: string; file_path: string; chunk_index: number; snippet: string }[] }>(
      `/api/kb/search?q=${encodeURIComponent(q)}`
    ),

  getSystemInfo: () => req<SystemInfo>('/api/system/info'),
  openApp: (app_name: string) =>
    req<Record<string, unknown>>('/api/system/open-app', { method: 'POST', body: JSON.stringify({ app_name }) }),
  getApprovals: () => req<PendingApproval[]>('/api/approvals'),
  resolveApproval: (id: string, approved: boolean) =>
    req<Record<string, unknown>>(`/api/approvals/${id}`, { method: 'POST', body: JSON.stringify({ approved }) }),
  getAudit: () => req<AuditItem[]>('/api/audit'),

  getSapiVoices: () => req<{ voices: string[] }>('/api/voice/sapi-voices'),
  speakSapi: async (text: string, voice = '', rate = 0): Promise<Blob> => {
    const res = await fetch('/api/voice/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice, rate }),
    })
    if (!res.ok) throw new Error('TTS failed')
    return res.blob()
  },

  getGoogleStatus: () => req<GoogleStatus>('/api/google/status'),
  saveGoogleCredentials: (credentials_json: string) =>
    req<{ ok: boolean; error?: string; path?: string }>('/api/google/credentials', {
      method: 'POST',
      body: JSON.stringify({ credentials_json }),
    }),
  connectGoogle: () => req<{ ok: boolean; error?: string }>('/api/google/connect', { method: 'POST' }),
  disconnectGoogle: () => req<{ ok: boolean }>('/api/google/disconnect', { method: 'POST' }),
  getGoogleSummary: () =>
    req<{ connected: boolean; events: Record<string, string>[]; emails: Record<string, string>[] }>('/api/google/summary'),
}
