import { useEffect, useState } from 'react'
import {
  Bot,
  Cloud,
  Mail,
  Palette,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Sliders,
  Trash2,
  User,
  Volume2,
} from 'lucide-react'
import { api } from '../api'
import type { GoogleStatus, QuickAction, Settings } from '../types'

interface SettingsViewProps {
  settings: Settings
  onUpdate: (patch: Record<string, unknown>) => Promise<void>
  onReset: () => Promise<void>
}

const ACCENT_PRESETS = [
  { label: 'Violet / Cyan', accent: '#7c5cff', secondary: '#22d3ee' },
  { label: 'Emerald / Teal', accent: '#10b981', secondary: '#2dd4bf' },
  { label: 'Rose / Amber', accent: '#f43f5e', secondary: '#fbbf24' },
  { label: 'Sky / Indigo', accent: '#0ea5e9', secondary: '#6366f1' },
  { label: 'Coral / Violet', accent: '#fb7185', secondary: '#a855f7' },
]

export function SettingsView({ settings, onUpdate, onReset }: SettingsViewProps) {
  const [section, setSection] = useState<'identity' | 'appearance' | 'ai' | 'voice' | 'capabilities' | 'google'>('identity')
  const [draft, setDraft] = useState<Settings>(settings)
  const [saving, setSaving] = useState(false)
  const [savedBanner, setSavedBanner] = useState('')

  const [ollamaInfo, setOllamaInfo] = useState<{ online: boolean; models: string[]; error?: string } | null>(null)
  const [sapiVoices, setSapiVoices] = useState<string[]>([])
  const [browserVoices, setBrowserVoices] = useState<string[]>([])
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus | null>(null)
  const [googleCredsText, setGoogleCredsText] = useState('')
  const [googleMsg, setGoogleMsg] = useState('')

  const [newQaLabel, setNewQaLabel] = useState('')
  const [newQaPrompt, setNewQaPrompt] = useState('')
  const [newAppAlias, setNewAppAlias] = useState('')
  const [newAppTarget, setNewAppTarget] = useState('')
  const [topicsInput, setTopicsInput] = useState(settings.briefing.topics.join(', '))

  useEffect(() => {
    setDraft(settings)
    setTopicsInput(settings.briefing.topics.join(', '))
  }, [settings])

  useEffect(() => {
    api.getOllamaModels().then(setOllamaInfo).catch(() => {})
    api.getSapiVoices().then((r) => setSapiVoices(r.voices)).catch(() => {})
    api.getGoogleStatus().then(setGoogleStatus).catch(() => {})
    if ('speechSynthesis' in window) {
      const loadVoices = () => {
        const vs = window.speechSynthesis.getVoices().map((v) => v.name)
        if (vs.length) setBrowserVoices(vs)
      }
      loadVoices()
      window.speechSynthesis.onvoiceschanged = loadVoices
    }
  }, [])

  const saveAll = async (customDraft?: Settings) => {
    setSaving(true)
    try {
      const target = customDraft || draft
      await onUpdate(target as unknown as Record<string, unknown>)
      setSavedBanner('Saved! Your customizations are live.')
      setTimeout(() => setSavedBanner(''), 2500)
    } finally {
      setSaving(false)
    }
  }

  const applyInstantAppearance = async (patch: Partial<Settings['appearance']>) => {
    const next = { ...draft, appearance: { ...draft.appearance, ...patch } }
    setDraft(next)
    await onUpdate({ appearance: next.appearance })
  }

  const addQuickAction = async () => {
    if (!newQaLabel.trim() || !newQaPrompt.trim()) return
    const item: QuickAction = {
      id: `qa_${Date.now()}`,
      label: newQaLabel.trim(),
      prompt: newQaPrompt.trim(),
      icon: 'sparkles',
    }
    const next = { ...draft, quick_actions: [...draft.quick_actions, item] }
    setDraft(next)
    setNewQaLabel('')
    setNewQaPrompt('')
    await onUpdate({ quick_actions: next.quick_actions })
  }

  const removeQuickAction = async (id: string) => {
    const next = { ...draft, quick_actions: draft.quick_actions.filter((q) => q.id !== id) }
    setDraft(next)
    await onUpdate({ quick_actions: next.quick_actions })
  }

  const addAllowedApp = async () => {
    if (!newAppAlias.trim() || !newAppTarget.trim()) return
    const allowed_apps = {
      ...draft.automation.allowed_apps,
      [newAppAlias.trim().toLowerCase()]: newAppTarget.trim(),
    }
    const next = { ...draft, automation: { ...draft.automation, allowed_apps } }
    setDraft(next)
    setNewAppAlias('')
    setNewAppTarget('')
    await onUpdate({ automation: next.automation })
  }

  const removeAllowedApp = async (alias: string) => {
    const allowed_apps = { ...draft.automation.allowed_apps }
    delete allowed_apps[alias]
    const next = { ...draft, automation: { ...draft.automation, allowed_apps } }
    setDraft(next)
    await onUpdate({ automation: next.automation })
  }

  const saveGoogleCreds = async () => {
    setGoogleMsg('')
    const res = await api.saveGoogleCredentials(googleCredsText)
    if (res.ok) {
      setGoogleMsg('Credentials saved! Click "Connect Google Account" to sign in.')
      setGoogleCredsText('')
      setGoogleStatus(await api.getGoogleStatus())
    } else {
      setGoogleMsg(res.error || 'Could not save credentials.')
    }
  }

  const connectGoogle = async () => {
    setGoogleMsg('Opening Google sign-in in your browser...')
    const res = await api.connectGoogle()
    setGoogleMsg(res.ok ? 'Connected to Google Calendar & Gmail!' : res.error || 'OAuth failed.')
    setGoogleStatus(await api.getGoogleStatus())
  }

  const disconnectGoogle = async () => {
    await api.disconnectGoogle()
    setGoogleMsg('Disconnected Google account.')
    setGoogleStatus(await api.getGoogleStatus())
  }

  return (
    <div className="page-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <h2 style={{ margin: 0 }}>{draft.identity.name} Customization Studio</h2>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Personalize identity, themes, AI models, voice, skills, shortcuts, and Google Workspace.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {savedBanner && <span style={{ color: 'var(--success)', fontSize: '0.85rem' }}>{savedBanner}</span>}
          <button
            className="btn"
            onClick={async () => {
              if (confirm('Reset all settings to defaults?')) await onReset()
            }}
          >
            <RotateCcw size={15} /> Reset Defaults
          </button>
          <button className="btn btn-primary" onClick={() => saveAll()} disabled={saving}>
            <Save size={15} /> {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button className={`btn ${section === 'identity' ? 'btn-primary' : ''}`} onClick={() => setSection('identity')}>
          <User size={15} /> Identity & Persona
        </button>
        <button className={`btn ${section === 'appearance' ? 'btn-primary' : ''}`} onClick={() => setSection('appearance')}>
          <Palette size={15} /> Appearance & Theme
        </button>
        <button className={`btn ${section === 'ai' ? 'btn-primary' : ''}`} onClick={() => setSection('ai')}>
          <Bot size={15} /> AI Engine (Cloud/Local)
        </button>
        <button className={`btn ${section === 'voice' ? 'btn-primary' : ''}`} onClick={() => setSection('voice')}>
          <Volume2 size={15} /> Voice & Speech
        </button>
        <button className={`btn ${section === 'capabilities' ? 'btn-primary' : ''}`} onClick={() => setSection('capabilities')}>
          <Sliders size={15} /> Skills, Briefing & Shortcuts
        </button>
        <button className={`btn ${section === 'google' ? 'btn-primary' : ''}`} onClick={() => setSection('google')}>
          <Mail size={15} /> Google Workspace
        </button>
      </div>

      {section === 'identity' && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="grid-2">
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Assistant Name</label>
              <input
                className="input"
                value={draft.identity.name}
                onChange={(e) => setDraft({ ...draft, identity: { ...draft.identity, name: e.target.value } })}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Your Name</label>
              <input
                className="input"
                placeholder="How should Lael address you?"
                value={draft.identity.user_name}
                onChange={(e) => setDraft({ ...draft, identity: { ...draft.identity, user_name: e.target.value } })}
              />
            </div>
          </div>

          <div className="grid-2">
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Home Greeting</label>
              <input
                className="input"
                value={draft.identity.greeting}
                onChange={(e) => setDraft({ ...draft, identity: { ...draft.identity, greeting: e.target.value } })}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Conversation Tone</label>
              <select
                className="select"
                value={draft.identity.tone}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    identity: { ...draft.identity, tone: e.target.value as Settings['identity']['tone'] },
                  })
                }
              >
                <option value="warm_concise">Warm & Concise</option>
                <option value="professional">Executive / Professional</option>
                <option value="playful">Creative & Playful</option>
                <option value="direct">Ultra-Direct & Bullet-Focused</option>
              </select>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>
              Custom System Prompt (Persona Instructions)
            </label>
            <textarea
              className="textarea"
              rows={5}
              value={draft.identity.system_prompt}
              onChange={(e) => setDraft({ ...draft, identity: { ...draft.identity, system_prompt: e.target.value } })}
            />
          </div>
        </div>
      )}

      {section === 'appearance' && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 8 }}>Theme Preset (Live Preview)</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {(['midnight', 'aurora', 'obsidian', 'forest', 'light'] as const).map((t) => (
                <button
                  key={t}
                  className={`btn ${draft.appearance.theme === t ? 'btn-primary' : ''}`}
                  onClick={() => applyInstantAppearance({ theme: t })}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 8 }}>Color Palettes & Custom Hex</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
              {ACCENT_PRESETS.map((p) => (
                <button
                  key={p.label}
                  className="btn"
                  onClick={() => applyInstantAppearance({ accent_color: p.accent, secondary_color: p.secondary })}
                >
                  <span style={{ width: 12, height: 12, borderRadius: 99, background: p.accent }} />
                  <span style={{ width: 12, height: 12, borderRadius: 99, background: p.secondary }} />
                  {p.label}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                Primary Accent:
                <input
                  type="color"
                  value={draft.appearance.accent_color}
                  onChange={(e) => applyInstantAppearance({ accent_color: e.target.value })}
                />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                Secondary Glow:
                <input
                  type="color"
                  value={draft.appearance.secondary_color}
                  onChange={(e) => applyInstantAppearance({ secondary_color: e.target.value })}
                />
              </label>
            </div>
          </div>

          <div className="grid-3">
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Voice Orb Style</label>
              <select
                className="select"
                value={draft.appearance.orb_style}
                onChange={(e) =>
                  applyInstantAppearance({ orb_style: e.target.value as Settings['appearance']['orb_style'] })
                }
              >
                <option value="aurora">Aurora Sphere</option>
                <option value="pulse">Pulse Wave</option>
                <option value="rings">Neon Rings</option>
                <option value="minimal">Minimal Ring</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Layout Density</label>
              <select
                className="select"
                value={draft.appearance.density}
                onChange={(e) =>
                  applyInstantAppearance({ density: e.target.value as Settings['appearance']['density'] })
                }
              >
                <option value="comfortable">Comfortable</option>
                <option value="compact">Compact</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>
                Text Scale ({Math.round(draft.appearance.font_scale * 100)}%)
              </label>
              <input
                type="range"
                min={0.85}
                max={1.2}
                step={0.05}
                value={draft.appearance.font_scale}
                onChange={(e) => applyInstantAppearance({ font_scale: parseFloat(e.target.value) })}
                style={{ width: '100%' }}
              />
            </div>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={draft.appearance.glass_effects}
              onChange={(e) => applyInstantAppearance({ glass_effects: e.target.checked })}
            />
            Enable Frosted Glass Blur Effects
          </label>
        </div>
      )}

      {section === 'ai' && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 8 }}>Active AI Backend</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                className={`btn ${draft.ai.provider === 'ollama' ? 'btn-primary' : ''}`}
                onClick={() => setDraft({ ...draft, ai: { ...draft.ai, provider: 'ollama' } })}
              >
                Local Ollama (Private / Offline)
              </button>
              <button
                className={`btn ${draft.ai.provider === 'gemini' ? 'btn-primary' : ''}`}
                onClick={() => setDraft({ ...draft, ai: { ...draft.ai, provider: 'gemini' } })}
              >
                <Cloud size={15} /> Cloud Gemini API
              </button>
              <button
                className={`btn ${draft.ai.provider === 'openai_compat' ? 'btn-primary' : ''}`}
                onClick={() => setDraft({ ...draft, ai: { ...draft.ai, provider: 'openai_compat' } })}
              >
                OpenAI-Compatible API
              </button>
            </div>
          </div>

          {draft.ai.provider === 'ollama' && (
            <div className="grid-2">
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Ollama URL</label>
                <input
                  className="input"
                  value={draft.ai.ollama_base_url}
                  onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, ollama_base_url: e.target.value } })}
                />
              </div>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <label style={{ fontSize: '0.82rem' }}>
                    Local Model ({ollamaInfo?.online ? `${ollamaInfo.models.length} detected` : 'Ollama offline'})
                  </label>
                  <button
                    className="btn btn-icon"
                    style={{ padding: '2px 6px', fontSize: '0.75rem' }}
                    onClick={() => api.getOllamaModels().then(setOllamaInfo)}
                  >
                    <RefreshCw size={12} /> Scan
                  </button>
                </div>
                {ollamaInfo?.models?.length ? (
                  <select
                    className="select"
                    value={draft.ai.ollama_model}
                    onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, ollama_model: e.target.value } })}
                  >
                    {!ollamaInfo.models.includes(draft.ai.ollama_model) && (
                      <option value={draft.ai.ollama_model}>{draft.ai.ollama_model}</option>
                    )}
                    {ollamaInfo.models.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="input"
                    value={draft.ai.ollama_model}
                    onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, ollama_model: e.target.value } })}
                  />
                )}
              </div>
            </div>
          )}

          {draft.ai.provider === 'gemini' && (
            <div className="grid-2">
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Gemini API Key</label>
                <input
                  className="input"
                  type="password"
                  placeholder="AIza..."
                  value={draft.ai.gemini_api_key}
                  onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, gemini_api_key: e.target.value } })}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Gemini Model</label>
                <select
                  className="select"
                  value={draft.ai.gemini_model}
                  onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, gemini_model: e.target.value } })}
                >
                  <option value="gemini-2.5-flash">gemini-2.5-flash (Fast & Smart)</option>
                  <option value="gemini-2.5-pro">gemini-2.5-pro (Deep Reasoning)</option>
                  <option value="gemini-2.0-flash">gemini-2.0-flash</option>
                </select>
              </div>
            </div>
          )}

          {draft.ai.provider === 'openai_compat' && (
            <div className="grid-3">
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Base URL</label>
                <input
                  className="input"
                  value={draft.ai.openai_base_url}
                  onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, openai_base_url: e.target.value } })}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>API Key</label>
                <input
                  className="input"
                  type="password"
                  value={draft.ai.openai_api_key}
                  onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, openai_api_key: e.target.value } })}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Model Name</label>
                <input
                  className="input"
                  value={draft.ai.openai_model}
                  onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, openai_model: e.target.value } })}
                />
              </div>
            </div>
          )}

          <div className="grid-2">
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>
                Creativity / Temperature ({draft.ai.temperature})
              </label>
              <input
                type="range"
                min={0}
                max={1.4}
                step={0.1}
                value={draft.ai.temperature}
                onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, temperature: parseFloat(e.target.value) } })}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>
                Max Agent Tool Steps ({draft.ai.max_tool_steps})
              </label>
              <input
                type="range"
                min={1}
                max={10}
                step={1}
                value={draft.ai.max_tool_steps}
                onChange={(e) => setDraft({ ...draft, ai: { ...draft.ai, max_tool_steps: parseInt(e.target.value, 10) } })}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </div>
      )}

      {section === 'voice' && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={draft.voice.enabled}
                onChange={(e) => setDraft({ ...draft, voice: { ...draft.voice, enabled: e.target.checked } })}
              />
              Enable Voice Input & Speech
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={draft.voice.auto_speak}
                onChange={(e) => setDraft({ ...draft, voice: { ...draft.voice, auto_speak: e.target.checked } })}
              />
              Automatically Speak Replies Aloud
            </label>
          </div>

          <div className="grid-2">
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Speech Engine</label>
              <select
                className="select"
                value={draft.voice.tts_engine}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    voice: { ...draft.voice, tts_engine: e.target.value as Settings['voice']['tts_engine'] },
                  })
                }
              >
                <option value="edge">Browser / Edge Natural Voices (Recommended)</option>
                <option value="windows_sapi">Offline Windows SAPI (System.Speech)</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Preferred Voice</label>
              <select
                className="select"
                value={draft.voice.edge_voice}
                onChange={(e) => setDraft({ ...draft, voice: { ...draft.voice, edge_voice: e.target.value } })}
              >
                <option value="">Default System Voice</option>
                {(draft.voice.tts_engine === 'windows_sapi' ? sapiVoices : browserVoices).map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid-2">
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Microphone Language (STT)</label>
              <input
                className="input"
                value={draft.voice.stt_language}
                onChange={(e) => setDraft({ ...draft, voice: { ...draft.voice, stt_language: e.target.value } })}
              />
            </div>
          </div>
        </div>
      )}

      {section === 'capabilities' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <strong style={{ display: 'block', marginBottom: 10 }}>Enabled Assistant Modules</strong>
            <div className="grid-3">
              {Object.entries(draft.capabilities).map(([key, enabled]) => (
                <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        capabilities: { ...draft.capabilities, [key]: e.target.checked },
                      })
                    }
                  />
                  {key.replace(/_/g, ' ')}
                </label>
              ))}
            </div>
          </div>

          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <strong>Daily Briefing Preferences</strong>
            <div className="grid-2">
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>Weather City</label>
                <input
                  className="input"
                  value={draft.briefing.location}
                  onChange={(e) => setDraft({ ...draft, briefing: { ...draft.briefing, location: e.target.value } })}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', marginBottom: 6 }}>News Topics (comma-separated)</label>
                <input
                  className="input"
                  value={topicsInput}
                  onChange={(e) => {
                    setTopicsInput(e.target.value)
                    setDraft({
                      ...draft,
                      briefing: {
                        ...draft.briefing,
                        topics: e.target.value
                          .split(',')
                          .map((s) => s.trim())
                          .filter(Boolean),
                      },
                    })
                  }}
                />
              </div>
            </div>
          </div>

          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <strong>Custom Home Quick Actions</strong>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                className="input"
                style={{ flex: 1, minWidth: 160 }}
                placeholder="Button label (e.g. Summarize Inbox)"
                value={newQaLabel}
                onChange={(e) => setNewQaLabel(e.target.value)}
              />
              <input
                className="input"
                style={{ flex: 2, minWidth: 220 }}
                placeholder="Prompt sent to Lael..."
                value={newQaPrompt}
                onChange={(e) => setNewQaPrompt(e.target.value)}
              />
              <button className="btn btn-primary" onClick={addQuickAction}>
                <Plus size={15} /> Add Shortcut
              </button>
            </div>
            {draft.quick_actions.map((qa) => (
              <div key={qa.id} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.86rem' }}>
                <strong>{qa.label}</strong>
                <span style={{ flex: 1, color: 'var(--text-muted)' }}>{qa.prompt}</span>
                <button className="btn btn-icon" onClick={() => removeQuickAction(qa.id)}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <strong>Windows Automation Guardrails & Custom Apps</strong>
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  checked={draft.automation.require_approval_for_shell}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      automation: { ...draft.automation, require_approval_for_shell: e.target.checked },
                    })
                  }
                />
                Always require approval before running PowerShell commands (Recommended)
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                className="input"
                style={{ flex: 1 }}
                placeholder="Alias (e.g. spotify)"
                value={newAppAlias}
                onChange={(e) => setNewAppAlias(e.target.value)}
              />
              <input
                className="input"
                style={{ flex: 2 }}
                placeholder="Executable or path (e.g. spotify.exe)"
                value={newAppTarget}
                onChange={(e) => setNewAppTarget(e.target.value)}
              />
              <button className="btn btn-primary" onClick={addAllowedApp}>
                <Plus size={15} /> Add App
              </button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {Object.entries(draft.automation.allowed_apps).map(([alias, target]) => (
                <div key={alias} className="tag" style={{ padding: '4px 10px', gap: 8 }}>
                  <span>
                    {alias} → {target}
                  </span>
                  <Trash2 size={12} style={{ cursor: 'pointer' }} onClick={() => removeAllowedApp(alias)} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {section === 'google' && (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
            <div>
              <strong>Google Calendar & Gmail Integration</strong>
              <div style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
                Status:{' '}
                <strong style={{ color: googleStatus?.connected ? 'var(--success)' : 'var(--warning)' }}>
                  {googleStatus?.connected
                    ? 'Connected'
                    : googleStatus?.credentials_found
                      ? 'Credentials ready — click Connect'
                      : 'Needs OAuth Desktop Credentials JSON'}
                </strong>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {googleStatus?.connected ? (
                <button className="btn btn-danger" onClick={disconnectGoogle}>
                  Disconnect Google
                </button>
              ) : (
                <button className="btn btn-primary" onClick={connectGoogle} disabled={!googleStatus?.credentials_found}>
                  Connect Google Account
                </button>
              )}
            </div>
          </div>

          {googleMsg && <div style={{ fontSize: '0.85rem', color: 'var(--secondary)' }}>{googleMsg}</div>}

          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            <strong>Quick Setup (One-Time):</strong>
            <ol style={{ margin: '6px 0 0', paddingLeft: 18 }}>
              <li>Open Google Cloud Console → APIs & Services → enable <strong>Google Calendar API</strong> and <strong>Gmail API</strong>.</li>
              <li>Create an <strong>OAuth 2.0 Client ID</strong> of type <strong>Desktop app</strong> and download the JSON file.</li>
              <li>Paste its contents below and click <strong>Save Credentials JSON</strong>, then click <strong>Connect Google Account</strong>.</li>
            </ol>
          </div>

          <textarea
            className="textarea"
            rows={5}
            placeholder='Paste your Google OAuth Desktop credentials JSON here ({"installed": {...}})...'
            value={googleCredsText}
            onChange={(e) => setGoogleCredsText(e.target.value)}
          />
          <div>
            <button className="btn" onClick={saveGoogleCreds} disabled={!googleCredsText.trim()}>
              Save Credentials JSON
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
