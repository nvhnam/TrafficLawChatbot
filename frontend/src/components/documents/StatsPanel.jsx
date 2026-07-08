import { Database, FileText } from '../icons'

export default function StatsPanel({ docCount, chunkCount }) {
  return (
    <div className="grid grid-cols-2 gap-4 mb-6">
      {[
        { Icon: FileText, label: 'Văn bản', value: docCount },
        { Icon: Database, label: 'Đoạn văn bản', value: chunkCount },
      ].map(({ Icon, label, value }) => (
        <div
          key={label}
          className="flex items-center gap-3 rounded-xl p-4"
          style={{ background: 'var(--surface2)', border: '1px solid var(--border)' }}
        >
          <div
            className="p-2 rounded-lg"
            style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}
          >
            <Icon size={18} />
          </div>
          <div>
            <div className="text-xl font-bold" style={{ color: 'var(--text)' }}>
              {value ?? '—'}
            </div>
            <div className="text-xs" style={{ color: 'var(--muted)' }}>
              {label}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
