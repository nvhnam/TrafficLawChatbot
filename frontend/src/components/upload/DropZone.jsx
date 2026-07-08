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
      className="rounded-xl flex flex-col items-center justify-center gap-3 py-10 cursor-pointer transition-colors select-none"
      style={{
        border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
        background: dragging ? 'var(--accent-dim)' : 'var(--surface2)',
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
        className="p-3 rounded-full"
        style={{ background: 'var(--accent-dim)', color: 'var(--accent)' }}
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
