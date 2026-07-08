import { useRef } from 'react'
import { Image, X } from '../icons'

export default function ImageUpload({ image, onChange }) {
  const inputRef = useRef(null)

  function handleFile(file) {
    if (!file || !file.type.startsWith('image/')) return
    const reader = new FileReader()
    reader.onload = e => onChange(e.target.result)
    reader.readAsDataURL(file)
  }

  function onInput(e) {
    handleFile(e.target.files?.[0])
    e.target.value = ''
  }

  function onDrop(e) {
    e.preventDefault()
    handleFile(e.dataTransfer.files?.[0])
  }

  return (
    <div>
      {image ? (
        <div className="relative inline-block">
          <img
            src={image}
            alt="attached"
            className="h-14 w-14 object-cover rounded-lg"
            style={{ border: '1px solid var(--border)' }}
          />
          <button
            className="absolute -top-1.5 -right-1.5 rounded-full p-0.5 cursor-pointer"
            style={{ background: 'var(--surface2)', color: 'var(--muted)' }}
            onClick={() => onChange(null)}
            title="Remove image"
          >
            <X size={10} />
          </button>
        </div>
      ) : (
        <button
          className="p-2 rounded-lg transition-colors cursor-pointer"
          style={{ color: 'var(--muted)', background: 'transparent' }}
          onClick={() => inputRef.current?.click()}
          onDragOver={e => e.preventDefault()}
          onDrop={onDrop}
          title="Attach image"
        >
          <Image size={18} />
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={onInput}
      />
    </div>
  )
}
