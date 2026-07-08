import { MessageSquare, BookOpen, Upload } from './icons'

const TABS = [
  { id: 'chat',      label: 'Chat',      Icon: MessageSquare },
  { id: 'documents', label: 'Documents', Icon: BookOpen },
  { id: 'upload',    label: 'Upload',    Icon: Upload },
]

export default function TabBar({ active, onChange }) {
  return (
    <header
      className="flex items-center gap-1 px-4 py-2 border-b shrink-0"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
    >
      <span
        className="text-sm font-semibold tracking-wide mr-4 select-none"
        style={{ color: 'var(--accent)' }}
      >
        VN Traffic Law
      </span>

      {TABS.map(({ id, label, Icon }) => {
        const isActive = active === id
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-colors cursor-pointer"
            style={{
              background: isActive ? 'var(--accent-dim)' : 'transparent',
              color: isActive ? 'var(--accent)' : 'var(--muted)',
              border: `1px solid ${isActive ? 'rgba(59,130,246,.3)' : 'transparent'}`,
            }}
          >
            <Icon size={14} />
            {label}
          </button>
        )
      })}
    </header>
  )
}
