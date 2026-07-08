import { useEffect, useState, useRef } from 'react'
import { checkProgress } from '../../lib/api'
import { CheckCircle, AlertCircle } from '../icons'

const PHASE_LABELS = {
  idle: 'Chờ xử lý',
  converting: 'Chuyển đổi PDF → Markdown',
  extracting: 'Trích xuất thực thể (Gemini)',
  chunking: 'Phân đoạn văn bản',
  uploading: 'Nhúng vào Neo4j',
  building: 'Xây dựng đồ thị',
  done: 'Hoàn tất',
  error: 'Lỗi',
}

export default function ProgressTracker({ active, onDone }) {
  const [state, setState] = useState(null)
  const timerRef = useRef(null)

  useEffect(() => {
    if (!active) return

    async function poll() {
      try {
        const data = await checkProgress()
        setState(data)
        if (data.phase === 'done' || data.phase === 'error' || !data.is_running) {
          if (data.phase === 'done') onDone?.()
          return
        }
      } catch { /* ignore transient errors */ }
      timerRef.current = setTimeout(poll, 1800)
    }

    poll()
    return () => clearTimeout(timerRef.current)
  }, [active, onDone])

  if (!state || !active) return null

  const isDone = state.phase === 'done'
  const isError = state.phase === 'error'
  const pct = state.total_files > 0
    ? Math.round((state.processed_files / state.total_files) * 100)
    : 0

  return (
    <div
      className="mt-4 rounded-xl px-4 py-4 space-y-3"
      style={{ background: 'var(--surface2)', border: '1px solid var(--border)' }}
    >
      {/* Phase label */}
      <div className="flex items-center gap-2">
        {isDone && <CheckCircle size={15} style={{ color: '#34d399' }} />}
        {isError && <AlertCircle size={15} style={{ color: '#f87171' }} />}
        {!isDone && !isError && (
          <div
            className="w-3.5 h-3.5 rounded-full border-2 border-t-transparent animate-spin shrink-0"
            style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }}
          />
        )}
        <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
          {PHASE_LABELS[state.phase] || state.phase}
        </span>
      </div>

      {/* Progress bar */}
      {state.total_files > 0 && (
        <div>
          <div
            className="h-1.5 rounded-full overflow-hidden"
            style={{ background: 'var(--border)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${pct}%`,
                background: isDone ? '#34d399' : isError ? '#f87171' : 'var(--accent)',
              }}
            />
          </div>
          <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--muted)' }}>
            <span>{state.current_file || state.message}</span>
            <span>{state.processed_files}/{state.total_files}</span>
          </div>
        </div>
      )}

      {!state.total_files && state.message && (
        <p className="text-xs" style={{ color: 'var(--muted)' }}>{state.message}</p>
      )}
    </div>
  )
}
