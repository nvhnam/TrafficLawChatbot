import { useState } from 'react'
import { ChevronDown, ChevronUp } from '../icons'

export default function SourcesPanel({ sources }) {
  const [open, setOpen] = useState(false)
  const entries = Object.entries(sources || {})
  if (entries.length === 0) return null

  return (
    <div className="sources-panel">
      <button
        className="sources-toggle"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
      >
        <span className="sources-count">{entries.length}</span>
        <span>nguồn tham khảo</span>
        <span className="sources-chevron">
          {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
        </span>
      </button>

      {open && (
        <ul className="sources-list">
          {entries.map(([key, src]) => (
            <li key={key} className="source-item">
              <div className="source-header">
                <span className="cite-chip">{key}</span>
                <span className="source-label">{src.label}</span>
              </div>
              <p className="source-text">{src.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
