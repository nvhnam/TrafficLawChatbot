import { useState } from 'react'
import { FileText, Trash2 } from '../icons'
import { deleteDocument } from '../../lib/api'

export default function DocumentCard({ doc, onDeleted }) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState(null)

  async function handleDelete() {
    if (!confirm(`Xóa văn bản "${doc.name}"?`)) return
    setDeleting(true)
    setError(null)
    try {
      await deleteDocument(doc.name)
      onDeleted(doc.name)
    } catch {
      setError('Xóa thất bại')
      setDeleting(false)
    }
  }

  return (
    <div className="surface-card flex items-center gap-3 px-4 py-3">
      <div
        className="p-2 rounded-lg shrink-0"
        style={{ background: 'var(--accent-dim)', color: 'var(--accent-hi)' }}
      >
        <FileText size={16} />
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate" style={{ color: 'var(--text)' }}>
          {doc.name}
        </div>
        <div className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
          {doc.chunk_count ?? '?'} đoạn
        </div>
        {error && <div className="text-xs mt-0.5" style={{ color: 'var(--danger)' }}>{error}</div>}
      </div>

      <button
        className="icon-btn shrink-0"
        onClick={handleDelete}
        disabled={deleting}
        title="Xóa văn bản"
        aria-label="Xóa văn bản"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}
