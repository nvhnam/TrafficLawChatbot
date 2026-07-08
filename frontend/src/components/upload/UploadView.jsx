import { useState, useCallback } from 'react'
import { uploadFiles, trainGraphSAGE } from '../../lib/api'
import DropZone from './DropZone'
import FileList from './FileList'
import ProgressTracker from './ProgressTracker'
import { Cpu, AlertCircle, CheckCircle } from '../icons'

export default function UploadView() {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [tracking, setTracking] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState(null)
  const [trainStatus, setTrainStatus] = useState(null)

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

  async function trainGraph() {
    setTrainStatus('loading')
    try {
      const res = await trainGraphSAGE()
      setTrainStatus(res.status === 'error' ? 'error' : 'done')
    } catch {
      setTrainStatus('error')
    }
  }

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

      {/* GraphSAGE opt-in section */}
      <div
        className="mt-8 pt-6"
        style={{ borderTop: '1px solid var(--border)' }}
      >
        <div className="flex items-start gap-3">
          <div
            className="p-2 rounded-lg shrink-0"
            style={{ background: 'var(--surface2)', color: 'var(--muted)' }}
          >
            <Cpu size={16} />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>
              Huấn luyện mô hình đồ thị (GraphSAGE)
            </p>
            <p className="text-xs mt-0.5 mb-3" style={{ color: 'var(--muted)' }}>
              Tùy chọn. Cải thiện độ chính xác truy vấn bằng cách học nhúng cấu trúc đồ thị. Tốn nhiều tài nguyên.
            </p>
            <button
              className="px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
              style={{
                background: trainStatus === 'loading' ? 'var(--border)' : 'var(--surface2)',
                color: trainStatus === 'done' ? '#34d399' : trainStatus === 'error' ? '#f87171' : 'var(--text)',
                border: '1px solid var(--border)',
              }}
              onClick={trainGraph}
              disabled={trainStatus === 'loading'}
            >
              {trainStatus === 'loading' && 'Đang huấn luyện...'}
              {trainStatus === 'done' && 'Hoàn tất!'}
              {trainStatus === 'error' && 'Thử lại'}
              {!trainStatus && 'Huấn luyện mô hình đồ thị'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
