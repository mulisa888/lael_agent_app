import { useEffect, useRef, useState } from 'react'
import {
  CheckSquare,
  Cpu,
  FolderSearch,
  Mic,
  MicOff,
  Send,
  Sparkles,
  Sun,
  Volume2,
  VolumeX,
  Wrench,
} from 'lucide-react'
import type { Message, Settings } from '../types'
import { VoiceOrb } from './VoiceOrb'

interface ChatViewProps {
  settings: Settings
  messages: Message[]
  sending: boolean
  orbState: 'idle' | 'listening' | 'thinking' | 'speaking'
  listening: boolean
  speaking: boolean
  onSend: (text: string) => void
  onToggleVoice: () => void
  onSpeakText: (text: string) => void
  onStopSpeaking: () => void
}

function QuickIcon({ name }: { name: string }) {
  switch (name) {
    case 'sun':
      return <Sun size={16} />
    case 'check':
      return <CheckSquare size={16} />
    case 'folder':
      return <FolderSearch size={16} />
    case 'cpu':
      return <Cpu size={16} />
    default:
      return <Sparkles size={16} />
  }
}

export function ChatView({
  settings,
  messages,
  sending,
  orbState,
  listening,
  speaking,
  onSend,
  onToggleVoice,
  onSpeakText,
  onStopSpeaking,
}: ChatViewProps) {
  const [draft, setDraft] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const submit = () => {
    const t = draft.trim()
    if (!t || sending) return
    setDraft('')
    onSend(t)
  }

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div
            style={{
              margin: 'auto',
              maxWidth: 680,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              gap: 18,
              padding: '24px 12px',
            }}
          >
            <VoiceOrb
              style={settings.appearance.orb_style}
              state={orbState}
              size={112}
              onClick={onToggleVoice}
              title={listening ? 'Stop listening' : `Talk to ${settings.identity.name}`}
            />
            <div>
              <h1 style={{ margin: '0 0 6px', fontSize: '1.7rem', letterSpacing: '-0.02em' }}>
                {settings.identity.greeting}
              </h1>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.94rem' }}>
                {listening
                  ? 'Listening... speak naturally.'
                  : `Click the orb to speak, or type below. Running on ${settings.ai.provider === 'ollama' ? `Ollama (${settings.ai.ollama_model})` : settings.ai.provider === 'gemini' ? `Gemini (${settings.ai.gemini_model})` : settings.ai.openai_model}.`}
              </p>
            </div>

            <div className="grid-2" style={{ width: '100%', marginTop: 6 }}>
              {settings.quick_actions.map((qa) => (
                <button
                  key={qa.id}
                  className="card"
                  onClick={() => onSend(qa.prompt)}
                  style={{
                    cursor: 'pointer',
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    color: 'var(--text)',
                    transition: 'border-color 0.15s',
                  }}
                >
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: 10,
                      display: 'grid',
                      placeItems: 'center',
                      background: 'color-mix(in srgb, var(--accent) 22%, transparent)',
                      color: 'var(--secondary)',
                      flexShrink: 0,
                    }}
                  >
                    <QuickIcon name={qa.icon} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.92rem' }}>{qa.label}</div>
                    <div
                      style={{
                        fontSize: '0.78rem',
                        color: 'var(--text-muted)',
                        display: '-webkit-box',
                        WebkitLineClamp: 1,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {qa.prompt}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`msg-row ${m.role}`}>
              <div className="msg-bubble">
                {m.role === 'assistant' && m.tool_events && m.tool_events.length > 0 && (
                  <div style={{ marginBottom: 10 }}>
                    {m.tool_events.map((ev, i) => (
                      <details key={i} className="tool-chip">
                        <summary style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Wrench size={13} /> Used tool: <strong>{ev.tool}</strong>
                        </summary>
                        <pre style={{ margin: '6px 0 0', fontSize: '0.73rem', overflowX: 'auto' }}>
                          {JSON.stringify({ arguments: ev.arguments, result: ev.result }, null, 2)}
                        </pre>
                      </details>
                    ))}
                  </div>
                )}
                <div>{m.content}</div>
                {m.role === 'assistant' && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 10,
                      marginTop: 8,
                      paddingTop: 6,
                      borderTop: '1px solid var(--border)',
                      fontSize: '0.74rem',
                      color: 'var(--text-muted)',
                    }}
                  >
                    <span>
                      {settings.identity.name}
                      {m.model ? ` · ${m.provider}/${m.model}` : ''}
                    </span>
                    <button
                      className="btn btn-icon"
                      style={{ padding: '3px 7px', fontSize: '0.74rem' }}
                      onClick={() => (speaking ? onStopSpeaking() : onSpeakText(m.content))}
                      title="Speak aloud"
                    >
                      {speaking ? <VolumeX size={13} /> : <Volume2 size={13} />}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {sending && (
          <div className="msg-row assistant">
            <div className="msg-bubble" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Sparkles size={16} color="var(--secondary)" />
              <span>{settings.identity.name} is thinking...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-composer">
        <div className="composer-inner">
          {settings.voice.enabled && (
            <button
              className={`btn btn-icon ${listening ? 'btn-primary' : ''}`}
              onClick={onToggleVoice}
              title={listening ? 'Stop voice input' : 'Voice input (Push to talk)'}
            >
              {listening ? <Mic size={18} /> : <MicOff size={18} />}
            </button>
          )}
          <input
            className="composer-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            placeholder={
              listening
                ? 'Listening via microphone...'
                : `Ask ${settings.identity.name} anything — tasks, files, web, calendar, or Windows commands...`
            }
          />
          {speaking && (
            <button className="btn btn-icon" onClick={onStopSpeaking} title="Stop speaking">
              <VolumeX size={18} />
            </button>
          )}
          <button className="btn btn-primary" onClick={submit} disabled={sending || !draft.trim()}>
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
