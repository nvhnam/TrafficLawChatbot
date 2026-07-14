import { FileText, X } from '../icons'

const EXT_COLOR = {
  pdf: '#f87171',
  docx: '#60a5fa', doc: '#60a5fa',
  png: '#34d399', jpg: '#34d399', jpeg: '#34d399', webp: '#34d399', tiff: '#34d399',
}

export default function FileList({ files, onRemove, disabled }) {
  if (files.length === 0) return null

  return (
    <ul className="space-y-1.5 mt-4">
      {files.map((file, i) => {
        const ext = file.name.split('.').pop().toLowerCase()
        const color = EXT_COLOR[ext] || 'var(--muted)'
        return (
          <li
            key={i}
            className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm transition-colors"
            style={{ background: 'var(--surface2)', border: '1px solid var(--border)' }}
          >
            <FileText size={14} style={{ color }} />
            <span className="flex-1 truncate" style={{ color: 'var(--text)' }}>
              {file.name}
            </span>
            <span
              className="text-xs px-1.5 py-0.5 rounded font-mono font-bold uppercase"
              style={{ background: 'var(--surface)', color }}
            >
              {ext}
            </span>
            {!disabled && (
              <button
                className="p-0.5 rounded cursor-pointer"
                style={{ color: 'var(--muted)' }}
                onClick={() => onRemove(i)}
                title="Bỏ tệp"
              >
                <X size={12} />
              </button>
            )}
          </li>
        )
      })}
    </ul>
  )
}
