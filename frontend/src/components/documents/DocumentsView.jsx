import { useState, useEffect, useCallback } from 'react'
import { fetchDocuments } from '../../lib/api'
import StatsPanel from './StatsPanel'
import DocumentCard from './DocumentCard'
import { RefreshCw, AlertCircle } from '../icons'

export default function DocumentsView() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const d = await fetchDocuments()
      setData(d)
    } catch {
      setError('Không thể tải danh sách văn bản.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  function handleDeleted(name) {
    setData(prev => ({
      ...prev,
      danh_sach_van_ban: prev.danh_sach_van_ban.filter(d => d.name !== name),
      tong_so_van_ban: (prev.tong_so_van_ban ?? prev.danh_sach_van_ban.length) - 1,
    }))
  }

  const docs = data?.danh_sach_van_ban ?? []
  const chunkCount = data?.tong_so_doan_van_ban ?? 0

  return (
    <div className="h-full overflow-y-auto px-6 py-6 max-w-3xl mx-auto w-full">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-bold" style={{ color: 'var(--text)' }}>
            Thư viện văn bản
          </h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
            Nguồn dữ liệu đã được nhúng vào đồ thị tri thức
          </p>
        </div>
        <button
          className="icon-btn"
          onClick={load}
          disabled={loading}
          title="Tải lại"
          aria-label="Tải lại danh sách"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {!loading && !error && (
        <StatsPanel docCount={docs.length} chunkCount={chunkCount} />
      )}

      {loading && (
        <div className="flex justify-center py-16">
          <div
            className="w-6 h-6 rounded-full border-2 border-t-transparent animate-spin"
            style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }}
          />
        </div>
      )}

      {error && (
        <div
          className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm"
          style={{ background: 'var(--danger-dim)', color: 'var(--danger)', border: '1px solid rgba(248,113,113,.25)' }}
        >
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {!loading && !error && docs.length === 0 && (
        <div className="surface-card text-center py-14 px-6 text-sm" style={{ color: 'var(--muted)' }}>
          Chưa có văn bản nào được nhúng. Hãy tải lên tài liệu ở tab Upload.
        </div>
      )}

      {!loading && !error && docs.length > 0 && (
        <div className="space-y-2">
          {docs.map(doc => (
            <DocumentCard key={doc.name} doc={doc} onDeleted={handleDeleted} />
          ))}
        </div>
      )}
    </div>
  )
}
