import { Database, FileText } from '../icons'

export default function StatsPanel({ docCount, chunkCount }) {
  return (
    <div className="grid grid-cols-2 gap-4 mb-6">
      {[
        { Icon: FileText, label: 'Văn bản', value: docCount },
        { Icon: Database, label: 'Đoạn văn bản', value: chunkCount },
      ].map(({ Icon, label, value }) => (
        <div key={label} className="surface-card flex items-center gap-3 p-4">
          <div
            className="p-2.5 rounded-lg"
            style={{ background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-2-solid) 100%)', color: '#fff' }}
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
