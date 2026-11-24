import { Mic, MicOff, Sparkles, Volume2 } from 'lucide-react'

interface VoiceOrbProps {
  style: 'aurora' | 'pulse' | 'rings' | 'minimal'
  state: 'idle' | 'listening' | 'thinking' | 'speaking'
  size?: number
  onClick?: () => void
  title?: string
}

export function VoiceOrb({ style, state, size = 92, onClick, title }: VoiceOrbProps) {
  const iconSize = Math.round(size * 0.34)
  return (
    <div
      className={`orb-wrap orb-${state}`}
      onClick={onClick}
      title={title || 'Click to toggle voice input'}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick?.()
      }}
    >
      <div
        className={`orb-core orb-${style}`}
        style={{ width: size, height: size }}
      >
        {state === 'listening' ? (
          <Mic size={iconSize} />
        ) : state === 'speaking' ? (
          <Volume2 size={iconSize} />
        ) : state === 'thinking' ? (
          <Sparkles size={iconSize} />
        ) : (
          <MicOff size={iconSize} opacity={0.9} />
        )}
      </div>
    </div>
  )
}
