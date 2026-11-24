import { Check, ShieldAlert, X } from 'lucide-react'
import type { PendingApproval } from '../types'

interface ApprovalModalProps {
  approvals: PendingApproval[]
  onDecision: (id: string, approved: boolean) => void
}

export function ApprovalModal({ approvals, onDecision }: ApprovalModalProps) {
  if (approvals.length === 0) return null
  const current = approvals[0]

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(5, 8, 16, 0.72)',
        backdropFilter: 'blur(8px)',
        display: 'grid',
        placeItems: 'center',
        zIndex: 1000,
        padding: 20,
      }}
    >
      <div
        className="card"
        style={{
          maxWidth: 540,
          width: '100%',
          borderColor: 'color-mix(in srgb, var(--warning) 60%, transparent)',
          padding: 22,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <ShieldAlert size={24} color="var(--warning)" />
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.05rem' }}>
              Permission Required (Tier {current.tier})
            </div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              {approvals.length > 1 ? `${approvals.length} pending actions` : 'Review carefully before approving'}
            </div>
          </div>
        </div>

        <div
          style={{
            padding: 12,
            borderRadius: 10,
            background: 'rgba(0,0,0,0.28)',
            border: '1px solid var(--border)',
            marginBottom: 14,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 6 }}>{current.summary}</div>
          <pre
            style={{
              margin: 0,
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {JSON.stringify(current.arguments, null, 2)}
          </pre>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn btn-danger" onClick={() => onDecision(current.id, false)}>
            <X size={16} /> Deny
          </button>
          <button className="btn btn-primary" onClick={() => onDecision(current.id, true)}>
            <Check size={16} /> Approve & Execute
          </button>
        </div>
      </div>
    </div>
  )
}
