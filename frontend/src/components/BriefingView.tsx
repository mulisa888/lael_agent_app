import { useEffect, useState } from 'react'
import { Calendar, CloudSun, Mail, Newspaper, RefreshCw, Volume2 } from 'lucide-react'
import { api } from '../api'

interface BriefingViewProps {
  onSpeakText: (text: string) => void
}

export function BriefingView({ onSpeakText }: BriefingViewProps) {
  const [data, setData] = useState<Record<string, any> | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      setData(await api.getBriefing())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh().catch(() => {})
  }, [])

  const speakBriefing = () => {
    if (!data) return
    const parts: string[] = [data.greeting, `Today is ${data.date_label}.`]
    if (data.weather?.ok) {
      parts.push(
        `In ${data.weather.location}, it is currently ${data.weather.temperature_c} degrees Celsius with ${data.weather.condition}.`
      )
    }
    const taskCount = (data.tasks || []).length
    parts.push(`You have ${taskCount} open ${taskCount === 1 ? 'task' : 'tasks'}.`)
    if (data.tasks?.length) {
      parts.push(`Top priority: ${data.tasks[0].title}.`)
    }
    onSpeakText(parts.join(' '))
  }

  return (
    <div className="page-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ margin: '0 0 4px' }}>{data?.greeting || 'Daily Briefing'}</h2>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{data?.date_label || 'Loading your day...'}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={speakBriefing} disabled={!data}>
            <Volume2 size={16} /> Read Aloud
          </button>
          <button className="btn btn-primary" onClick={refresh} disabled={loading}>
            <RefreshCw size={16} /> {loading ? 'Refreshing...' : 'Refresh Briefing'}
          </button>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontWeight: 700 }}>
            <CloudSun size={18} color="var(--secondary)" /> Weather
          </div>
          {data?.weather?.ok ? (
            <div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800 }}>
                {data.weather.temperature_c}°C <span style={{ fontSize: '1rem', fontWeight: 500, color: 'var(--text-muted)' }}>{data.weather.condition}</span>
              </div>
              <div style={{ color: 'var(--text-muted)', marginTop: 4 }}>
                {data.weather.location} · High {data.weather.high_c}° / Low {data.weather.low_c}° · Rain {data.weather.rain_chance_pct ?? 0}%
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)' }}>
              {data?.weather?.error || 'Configure your city in Settings -> Daily Briefing.'}
            </div>
          )}
        </div>

        <div className="card">
          <div style={{ fontWeight: 700, marginBottom: 10 }}>Open Tasks & Reminders</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(data?.tasks || []).slice(0, 5).map((t: any) => (
              <div key={t.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                <span>• {t.title}</span>
                <span className="tag">{t.priority}</span>
              </div>
            ))}
            {(!data?.tasks || data.tasks.length === 0) && (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>All clear — no open tasks!</div>
            )}
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontWeight: 700 }}>
            <Calendar size={18} color="var(--accent)" /> Google Calendar & <Mail size={18} color="var(--secondary)" /> Gmail
          </div>
          {data?.google?.connected ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4 }}>Upcoming Events</div>
                {(data.google.events || []).map((ev: any) => (
                  <div key={ev.id} style={{ fontSize: '0.88rem', marginBottom: 4 }}>
                    <strong>{ev.summary}</strong> — <span style={{ color: 'var(--text-muted)' }}>{ev.start}</span>
                  </div>
                ))}
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 4 }}>Recent Emails</div>
                {(data.google.emails || []).slice(0, 3).map((em: any) => (
                  <div key={em.id} style={{ fontSize: '0.86rem', marginBottom: 4 }}>
                    <strong>{em.subject}</strong> <span style={{ color: 'var(--text-muted)' }}>({em.from})</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
              Google Calendar & Gmail not connected yet. Connect anytime in <strong>Settings → Google Workspace</strong>.
            </div>
          )}
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontWeight: 700 }}>
            <Newspaper size={18} color="var(--secondary)" /> Curated Web Headlines
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {(data?.news || []).map((n: any, idx: number) => (
              <a
                key={idx}
                href={n.url}
                target="_blank"
                rel="noreferrer"
                style={{ textDecoration: 'none', color: 'inherit', paddingBottom: 8, borderBottom: '1px solid var(--border)' }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{n.title}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{n.snippet}</div>
              </a>
            ))}
            {(!data?.news || data.news.length === 0) && (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                Customize your news topics in Settings → Daily Briefing.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
