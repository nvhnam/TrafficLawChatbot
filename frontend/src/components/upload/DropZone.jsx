import { useRef, useState } from 'react'
import { Upload } from '../icons'

const ACCEPTED = '.pdf,.docx,.doc,.png,.jpg,.jpeg,.webp,.tiff'

export default function DropZone({ onFiles }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  function collect(fileList) {
    const files = Array.from(fileList).filter(f => {
      const ext = '.' + f.name.split('.').pop().toLowerCase()
      return ACCEPTED.split(',').includes(ext)
    })
    if (files.length) onFiles(files)
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    collect(e.dataTransfer.files)
  }

  return (
    <div
      className="rounded-2xl flex flex-col items-center justify-center gap-3 py-12 cursor-pointer transition-all duration-200 select-none"
      style={{
        border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
        background: dragging ? 'var(--accent-dim)' : 'var(--surface2)',
        transform: dragging ? 'scale(1.01)' : 'scale(1)',
      }}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()}
    >
      <div
        className="p-3.5 rounded-full"
        style={{ background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-2-solid) 100%)', color: '#fff', boxShadow: '0 4px 16px rgba(59,130,246,.35)' }}
      >
        <Upload size={22} />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>
          Kéo thả tệp vào đây
        </p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
          PDF, DOCX, PNG, JPG, WEBP, TIFF
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED}
        className="hidden"
        onChange={e => { collect(e.target.files); e.target.value = '' }}
      />
    </div>
  )
}
