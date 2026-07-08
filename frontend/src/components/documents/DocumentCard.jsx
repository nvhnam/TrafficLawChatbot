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
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-xl transition-colors"
      style={{ background: 'var(--surface2)', border: '1px solid var(--border)' }}
    >
      <div
        className="p-2 rounded-lg shrink-0"
        style={{ background: 'var(--surface)', color: 'var(--muted)' }}
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
        {error && <div className="text-xs mt-0.5 text-red-400">{error}</div>}
      </div>

      <button
        className="p-1.5 rounded-lg transition-colors cursor-pointer shrink-0"
        style={{ color: deleting ? 'var(--muted)' : 'var(--muted)' }}
        onClick={handleDelete}
        disabled={deleting}
        title="Xóa văn bản"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}
