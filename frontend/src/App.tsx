import { useEffect, useRef, useState } from 'react'
import {
  CheckSquare,
  FolderSearch,
  MessageSquare,
  Plus,
  Settings as SettingsIcon,
  Shield,
  Sun,
  Trash2,
} from 'lucide-react'
import { api } from './api'
import { ApprovalModal } from './components/ApprovalModal'
import { AutomationView } from './components/AutomationView'
import { BriefingView } from './components/BriefingView'
import { ChatView } from './components/ChatView'
import { KnowledgeView } from './components/KnowledgeView'
import { ProductivityView } from './components/ProductivityView'
import { SettingsView } from './components/SettingsView'
import type { Conversation, Message, PendingApproval, Settings } from './types'

type NavTab = 'chat' | 'briefing' | 'productivity' | 'knowledge' | 'automation' | 'settings'

export default function App() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [tab, setTab] = useState<NavTab>('chat')
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [sending, setSending] = useState(false)
  const [approvals, setApprovals] = useState<PendingApproval[]>([])

  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const recognitionRef = useRef<any>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const refreshApprovals = () => {
    api.getApprovals().then(setApprovals).catch(() => {})
  }

  useEffect(() => {
    Promise.all([api.getSettings(), api.listConversations(), api.getApprovals()])
      .then(([s, convs, apps]) => {
        setSettings(s)
        setConversations(convs)
        setApprovals(apps)
      })
      .catch(() => {})

    const timer = setInterval(refreshApprovals, 6000)
    return () => clearInterval(timer)
  }, [])

  // Apply live customization theme variables
  useEffect(() => {
    if (!settings) return
    const root = document.documentElement
    root.setAttribute('data-theme', settings.appearance.theme)
    root.setAttribute('data-density', settings.appearance.density)
    root.setAttribute('data-glass', String(settings.appearance.glass_effects))
    root.style.setProperty('--accent', settings.appearance.accent_color)
    root.style.setProperty('--secondary', settings.appearance.secondary_color)
    root.style.setProperty('--font-scale', String(settings.appearance.font_scale))
    document.title = `${settings.identity.name} — Personal Assistant`
  }, [settings])

  const openConversation = async (id: string) => {
    setActiveConvId(id)
    setTab('chat')
    const data = await api.getConversation(id)
    setMessages(data.messages)
  }

  const startNewChat = () => {
    setActiveConvId(null)
    setMessages([])
    setTab('chat')
  }

  const deleteConv = async (id: string) => {
    await api.deleteConversation(id)
    setConversations((prev) => prev.filter((c) => c.id !== id))
    if (activeConvId === id) {
      setActiveConvId(null)
      setMessages([])
    }
  }

  const stopSpeaking = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setSpeaking(false)
  }

  const speakText = async (text: string) => {
    if (!settings?.voice.enabled || !text.trim()) return
    stopSpeaking()
    const clean = text.replace(/[*#`_]/g, '').slice(0, 1200)

    if (settings.voice.tts_engine === 'windows_sapi') {
      try {
        setSpeaking(true)
        const blob = await api.speakSapi(clean, settings.voice.edge_voice)
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio
        audio.onended = () => {
          setSpeaking(false)
          URL.revokeObjectURL(url)
        }
        audio.onerror = () => setSpeaking(false)
        await audio.play()
        return
      } catch {
        setSpeaking(false)
      }
    }

    if ('speechSynthesis' in window) {
      const utter = new SpeechSynthesisUtterance(clean)
      const voices = window.speechSynthesis.getVoices()
      const preferred =
        voices.find((v) => v.name === settings.voice.edge_voice) ||
        voices.find((v) => v.name.toLowerCase().includes('natural') && v.lang.startsWith('en')) ||
        voices.find((v) => v.lang.startsWith('en'))
      if (preferred) utter.voice = preferred
      utter.onstart = () => setSpeaking(true)
      utter.onend = () => setSpeaking(false)
      utter.onerror = () => setSpeaking(false)
      window.speechSynthesis.speak(utter)
    }
  }

  const handleSend = async (text: string) => {
    if (sending) return
    setSending(true)
    const optimistic: Message = {
      id: `tmp_${Date.now()}`,
      conversation_id: activeConvId || 'pending',
      role: 'user',
      content: text,
      tool_events: [],
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, optimistic])

    try {
      const res = await api.chat(activeConvId, text)
      setActiveConvId(res.conversation_id)
      setMessages((prev) => [...prev.filter((m) => m.id !== optimistic.id), { ...optimistic, conversation_id: res.conversation_id }, res.message])
      setApprovals(res.pending_approvals || [])
      setConversations(await api.listConversations())
      if (settings?.voice.auto_speak && res.message.content) {
        speakText(res.message.content)
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          conversation_id: activeConvId || 'err',
          role: 'assistant',
          content: `Error talking to backend: ${err instanceof Error ? err.message : String(err)}`,
          tool_events: [],
          created_at: new Date().toISOString(),
        },
      ])
    } finally {
      setSending(false)
    }
  }

  const toggleVoice = () => {
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop()
      setListening(false)
      return
    }
    const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRec) {
      alert('Voice microphone input requires Microsoft Edge or Chrome (Web Speech API).')
      return
    }
    stopSpeaking()
    const rec = new SpeechRec()
    rec.lang = settings?.voice.stt_language || 'en-US'
    rec.interimResults = false
    rec.maxAlternatives = 1
    rec.onstart = () => setListening(true)
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    rec.onresult = (event: any) => {
      const transcript = event.results?.[0]?.[0]?.transcript
      if (transcript) {
        handleSend(transcript)
      }
    }
    recognitionRef.current = rec
    rec.start()
  }

  const handleApprovalDecision = async (id: string, approved: boolean) => {
    const res = await api.resolveApproval(id, approved)
    refreshApprovals()
    if (activeConvId) {
      const statusText = approved
        ? `Approved action (${id}). Result:\n${JSON.stringify(res.result ?? res, null, 2)}`
        : `Denied action (${id}).`
      setMessages((prev) => [
        ...prev,
        {
          id: `app_${Date.now()}`,
          conversation_id: activeConvId,
          role: 'assistant',
          content: statusText,
          tool_events: [],
          created_at: new Date().toISOString(),
        },
      ])
    }
  }

  const handleUpdateSettings = async (patch: Record<string, unknown>) => {
    const updated = await api.updateSettings(patch)
    setSettings(updated)
  }

  const handleResetSettings = async () => {
    const updated = await api.resetSettings()
    setSettings(updated)
  }

  if (!settings) {
    return (
      <div style={{ height: '100vh', display: 'grid', placeItems: 'center', color: 'var(--text-muted)' }}>
        Starting Lael Personal Assistant...
      </div>
    )
  }

  const orbState = listening ? 'listening' : sending ? 'thinking' : speaking ? 'speaking' : 'idle'
  const activeModelLabel =
    settings.ai.provider === 'ollama'
      ? `Ollama · ${settings.ai.ollama_model}`
      : settings.ai.provider === 'gemini'
        ? `Gemini · ${settings.ai.gemini_model}`
        : `API · ${settings.ai.openai_model}`

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-box">
          <div className="brand-badge">{settings.identity.name.slice(0, 1).toUpperCase()}</div>
          <div style={{ minWidth: 0 }}>
            <div className="brand-title">{settings.identity.name}</div>
            <div className="brand-sub">{settings.identity.tagline}</div>
          </div>
        </div>

        <nav className="nav-list">
          <button className={`nav-btn ${tab === 'chat' ? 'active' : ''}`} onClick={() => setTab('chat')}>
            <MessageSquare size={17} /> Assistant Chat
          </button>
          <button className={`nav-btn ${tab === 'briefing' ? 'active' : ''}`} onClick={() => setTab('briefing')}>
            <Sun size={17} /> Daily Briefing
          </button>
          <button className={`nav-btn ${tab === 'productivity' ? 'active' : ''}`} onClick={() => setTab('productivity')}>
            <CheckSquare size={17} /> Tasks & Notes
          </button>
          <button className={`nav-btn ${tab === 'knowledge' ? 'active' : ''}`} onClick={() => setTab('knowledge')}>
            <FolderSearch size={17} /> Knowledge Base
          </button>
          <button className={`nav-btn ${tab === 'automation' ? 'active' : ''}`} onClick={() => setTab('automation')}>
            <Shield size={17} /> Windows & Safety
            {approvals.length > 0 && <span className="badge-pill">{approvals.length}</span>}
          </button>
          <button className={`nav-btn ${tab === 'settings' ? 'active' : ''}`} onClick={() => setTab('settings')}>
            <SettingsIcon size={17} /> Customize
          </button>
        </nav>

        <div className="conv-section">
          <div className="conv-header">
            <span>Conversations</span>
            <button className="btn btn-icon" style={{ padding: 4 }} onClick={startNewChat} title="New chat">
              <Plus size={14} />
            </button>
          </div>
          <div className="conv-list">
            {conversations.map((c) => (
              <div
                key={c.id}
                className={`conv-item ${activeConvId === c.id && tab === 'chat' ? 'active' : ''}`}
                onClick={() => openConversation(c.id)}
              >
                <span className="conv-item-title">{c.title}</span>
                <Trash2
                  size={13}
                  style={{ opacity: 0.6, flexShrink: 0 }}
                  onClick={(e) => {
                    e.stopPropagation()
                    deleteConv(c.id)
                  }}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="provider-pill" onClick={() => setTab('settings')} title="Switch AI engine or customize">
          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{activeModelLabel}</div>
          <span className="tag">{settings.ai.provider === 'ollama' ? 'Local' : 'Cloud'}</span>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div style={{ fontWeight: 700, fontSize: '0.98rem' }}>
            {tab === 'chat' && `${settings.identity.name} · Voice & Chat`}
            {tab === 'briefing' && 'Daily Briefing'}
            {tab === 'productivity' && 'Tasks, Notes & Reminders'}
            {tab === 'knowledge' && 'Personal Knowledge Base'}
            {tab === 'automation' && 'Windows System & Safety'}
            {tab === 'settings' && 'Customization Studio'}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              className="btn"
              style={{ fontSize: '0.8rem', padding: '5px 10px' }}
              onClick={() =>
                handleUpdateSettings({
                  ai: { provider: settings.ai.provider === 'ollama' ? 'gemini' : 'ollama' },
                })
              }
              title="Quick switch between Local Ollama and Cloud Gemini"
            >
              Switch to {settings.ai.provider === 'ollama' ? 'Cloud Gemini' : 'Local Ollama'}
            </button>
            <button
              className={`btn ${settings.voice.auto_speak ? 'btn-primary' : ''}`}
              style={{ fontSize: '0.8rem', padding: '5px 10px' }}
              onClick={() =>
                handleUpdateSettings({
                  voice: { auto_speak: !settings.voice.auto_speak },
                })
              }
            >
              Voice Replies: {settings.voice.auto_speak ? 'ON' : 'OFF'}
            </button>
          </div>
        </header>

        {tab === 'chat' && (
          <ChatView
            settings={settings}
            messages={messages}
            sending={sending}
            orbState={orbState}
            listening={listening}
            speaking={speaking}
            onSend={handleSend}
            onToggleVoice={toggleVoice}
            onSpeakText={speakText}
            onStopSpeaking={stopSpeaking}
          />
        )}
        {tab === 'briefing' && <BriefingView onSpeakText={speakText} />}
        {tab === 'productivity' && <ProductivityView />}
        {tab === 'knowledge' && <KnowledgeView />}
        {tab === 'automation' && (
          <AutomationView settings={settings} approvals={approvals} onDecision={handleApprovalDecision} />
        )}
        {tab === 'settings' && (
          <SettingsView settings={settings} onUpdate={handleUpdateSettings} onReset={handleResetSettings} />
        )}
      </main>

      <ApprovalModal approvals={approvals} onDecision={handleApprovalDecision} />
    </div>
  )
}
