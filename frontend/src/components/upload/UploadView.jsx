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
      <h2 className="text-base font-semibold mb-5" style={{ color: 'var(--text)' }}>
        Tải lên văn bản
      </h2>

      <DropZone onFiles={addFiles} />
      <FileList files={files} onRemove={removeFile} disabled={uploading} />

      {error && (
        <div
          className="flex items-center gap-2 mt-4 px-4 py-3 rounded-xl text-sm"
          style={{ background: 'rgba(239,68,68,.1)', color: '#f87171', border: '1px solid rgba(239,68,68,.2)' }}
        >
          <AlertCircle size={15} /> {error}
        </div>
      )}

      {done && !error && (
        <div
          className="flex items-center gap-2 mt-4 px-4 py-3 rounded-xl text-sm"
          style={{ background: 'rgba(52,211,153,.1)', color: '#34d399', border: '1px solid rgba(52,211,153,.2)' }}
        >
          <CheckCircle size={15} /> Nhúng hoàn tất!
        </div>
      )}

      <ProgressTracker active={tracking} onDone={handleDone} />

      {files.length > 0 && !uploading && (
        <button
          className="mt-5 w-full py-2.5 rounded-xl text-sm font-semibold transition-colors cursor-pointer"
          style={{ background: 'var(--accent)', color: '#fff' }}
          onClick={submit}
        >
          Nhúng {files.length} tệp vào đồ thị
        </button>
      )}
    </div>
  )
}
