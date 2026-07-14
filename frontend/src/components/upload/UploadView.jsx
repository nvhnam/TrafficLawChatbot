import { useState, useCallback } from 'react'
import { uploadFiles } from '../../lib/api'
import DropZone from './DropZone'
import FileList from './FileList'
import ProgressTracker from './ProgressTracker'
import { AlertCircle, CheckCircle } from '../icons'

export default function UploadView() {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [tracking, setTracking] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState(null)

  function addFiles(incoming) {
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name))
      return [...prev, ...incoming.filter(f => !names.has(f.name))]
    })
    setDone(false)
    setError(null)
  }

  function removeFile(i) {
    setFiles(prev => prev.filter((_, j) => j !== i))
  }

  async function submit() {
    if (!files.length || uploading) return
    setUploading(true)
    setError(null)
    setDone(false)

    const formData = new FormData()
    files.forEach(f => formData.append('files', f))

    try {
      const res = await uploadFiles(formData)
      if (res.status === 'error') throw new Error(res.message)
      setTracking(true)
    } catch (err) {
      setError(err.message || 'Tải lên thất bại.')
      setUploading(false)
    }
  }

  const handleDone = useCallback(() => {
    setUploading(false)
    setTracking(false)
    setDone(true)
    setFiles([])
  }, [])

  return (
    <div className="h-full overflow-y-auto px-6 py-6 max-w-2xl mx-auto w-full">
      <div className="mb-5">
        <h2 className="text-lg font-bold" style={{ color: 'var(--text)' }}>
          Tải lên văn bản
        </h2>
        <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
          Thêm tài liệu mới để nhúng vào đồ thị tri thức
        </p>
      </div>

      <DropZone onFiles={addFiles} />
      <FileList files={files} onRemove={removeFile} disabled={uploading} />

      {error && (
        <div
          className="flex items-center gap-2 mt-4 px-4 py-3 rounded-xl text-sm"
          style={{ background: 'var(--danger-dim)', color: 'var(--danger)', border: '1px solid rgba(248,113,113,.25)' }}
        >
          <AlertCircle size={15} /> {error}
        </div>
      )}

      {done && !error && (
        <div
          className="flex items-center gap-2 mt-4 px-4 py-3 rounded-xl text-sm"
          style={{ background: 'var(--success-dim)', color: 'var(--success)', border: '1px solid rgba(52,211,153,.25)' }}
        >
          <CheckCircle size={15} /> Nhúng hoàn tất!
        </div>
      )}

      <ProgressTracker active={tracking} onDone={handleDone} />

      {files.length > 0 && !uploading && (
        <button
          className="mt-5 w-full py-2.5 rounded-xl text-sm font-semibold cursor-pointer transition-all"
          style={{
            background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-2-solid) 100%)',
            color: '#fff',
            boxShadow: '0 4px 16px rgba(59,130,246,.35)',
          }}
          onClick={submit}
        >
          Nhúng {files.length} tệp vào đồ thị
        </button>
      )}
    </div>
  )
}
