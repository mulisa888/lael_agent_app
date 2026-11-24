import { useEffect, useState } from 'react'
import { Activity, Battery, Check, Cpu, HardDrive, Play, RefreshCw, Shield, X } from 'lucide-react'
import { api } from '../api'
import type { AuditItem, PendingApproval, Settings, SystemInfo } from '../types'

interface AutomationViewProps {
  settings: Settings
  approvals: PendingApproval[]
  onDecision: (id: string, approved: boolean) => void
}

export function AutomationView({ settings, approvals, onDecision }: AutomationViewProps) {
  const [sys, setSys] = useState<SystemInfo | null>(null)
  const [audit, setAudit] = useState<AuditItem[]>([])
  const [launchMsg, setLaunchMsg] = useState('')

  const load = async () => {
    const [s, a] = await Promise.all([api.getSystemInfo(), api.getAudit()])
    setSys(s)
    setAudit(a)
  }

  useEffect(() => {
    load().catch(() => {})
  }, [])

  const launch = async (alias: string) => {
    const res = await api.openApp(alias)
    setLaunchMsg(res.ok ? `Launched ${alias}` : String(res.error || 'Failed to launch'))
    setTimeout(() => setLaunchMsg(''), 3000)
  }

  return (
    <div className="page-scroll" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ margin: 0 }}>Windows System & Automation</h2>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Live PC telemetry, quick app launchers, Tier 3 approval queue, and execution audit log.
          </div>
        </div>
        <button className="btn" onClick={load}>
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      <div className="grid-3">
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)' }}>
            <Cpu size={16} /> CPU Load
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, marginTop: 6 }}>
            {sys?.cpu_percent !== undefined && sys?.cpu_percent !== null ? `${sys.cpu_percent}%` : '—'}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{sys?.computer_name || sys?.os}</div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)' }}>
            <Activity size={16} /> Memory (RAM)
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, marginTop: 6 }}>
            {sys?.memory_percent !== undefined ? `${sys.memory_percent}%` : '—'}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {sys?.memory_used_gb ?? '?'} / {sys?.memory_total_gb ?? '?'} GB
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)' }}>
            <HardDrive size={16} /> Disk (C:) & <Battery size={16} /> Battery
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, marginTop: 6 }}>
            {sys ? `${sys.disk_percent}%` : '—'}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {sys ? `${sys.disk_used_gb}/${sys.disk_total_gb} GB` : ''}
            {sys?.battery_percent !== null && sys?.battery_percent !== undefined
              ? ` · Battery ${sys.battery_percent}%`
              : ''}
          </div>
        </div>
      </div>

      {approvals.length > 0 && (
        <div className="card" style={{ borderColor: 'var(--warning)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, marginBottom: 10 }}>
            <Shield size={18} color="var(--warning)" /> Pending Tier 3 Approvals ({approvals.length})
          </div>
          {approvals.map((a) => (
            <div
              key={a.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 10,
                padding: '10px 0',
                borderTop: '1px solid var(--border)',
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>{a.summary}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{a.tool_name}</div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-danger" onClick={() => onDecision(a.id, false)}>
                  <X size={15} /> Deny
                </button>
                <button className="btn btn-primary" onClick={() => onDecision(a.id, true)}>
                  <Check size={15} /> Approve
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <strong>Quick App Launchers (Customizable in Settings)</strong>
          {launchMsg && <span style={{ fontSize: '0.82rem', color: 'var(--secondary)' }}>{launchMsg}</span>}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {Object.keys(settings.automation.allowed_apps).map((alias) => (
            <button key={alias} className="btn" onClick={() => launch(alias)}>
              <Play size={14} /> {alias}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <strong style={{ display: 'block', marginBottom: 10 }}>Action Audit Log</strong>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 280, overflowY: 'auto' }}>
          {audit.map((a) => (
            <div
              key={a.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: '0.84rem',
                paddingBottom: 6,
                borderBottom: '1px solid var(--border)',
              }}
            >
              <span className="tag">T{a.tier}</span>
              <span style={{ flex: 1 }}>{a.summary}</span>
              <span className="tag">{a.status}</span>
            </div>
          ))}
          {audit.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No tool actions logged yet.</div>}
        </div>
      </div>
    </div>
  )
}
