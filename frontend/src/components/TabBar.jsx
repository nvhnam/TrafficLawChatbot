import { MessageSquare, BookOpen, Upload, Shield } from './icons'

const TABS = [
  { id: 'chat',      label: 'Chat',      Icon: MessageSquare },
  { id: 'documents', label: 'Documents', Icon: BookOpen },
  { id: 'upload',    label: 'Upload',    Icon: Upload },
]

export default function TabBar({ active, onChange }) {
  return (
    <header className="app-header">
      <div className="header-logo">
        <div className="header-logo-badge">
          <Shield size={16} />
        </div>
        <div className="header-logo-text">
          <span className="header-logo-title">VN Traffic Law</span>
          <span className="header-logo-sub">AI ASSISTANT</span>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="Điều hướng chính">
        {TABS.map(({ id, label, Icon }) => {
          const isActive = active === id
          return (
            <button
              key={id}
              onClick={() => onChange(id)}
              className={`nav-tab${isActive ? ' nav-tab--active' : ''}`}
              aria-current={isActive ? 'page' : undefined}
              title={label}
            >
              <Icon size={15} />
              <span className="nav-tab-label">{label}</span>
            </button>
          )
        })}
      </nav>
    </header>
  )
}
