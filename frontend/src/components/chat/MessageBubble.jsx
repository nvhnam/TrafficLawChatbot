import { marked } from 'marked'
import { useRef, useEffect, useState, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { X } from '../icons'

marked.setOptions({ breaks: true, gfm: true })

const CITE_RE = /\[\[S\d+\]\]/g

function injectCiteHTML(text) {
  return (text || '').replace(CITE_RE, (match) => {
    const key = match.slice(2, -2)
    return `<button class="cite-chip" data-cite-key="${key}" tabindex="0" aria-label="Nguồn ${key}">${key}</button>`
  })
}

// ── Floating tooltip ────────────────────────────────────────────────────────
function CiteTooltip({ anchorRect, source }) {
  const ref = useRef(null)
  const [pos, setPos] = useState({ x: -9999, y: -9999, ready: false })

  useEffect(() => {
    if (!ref.current || !anchorRect) return
    const el = ref.current
    const GAP = 10
    const vw = window.innerWidth
    const tw = el.offsetWidth
    const th = el.offsetHeight

    let x = anchorRect.left
    let y = anchorRect.top - th - GAP
    if (y < GAP) y = anchorRect.bottom + GAP
    if (x + tw > vw - GAP) x = vw - tw - GAP
    if (x < GAP) x = GAP

    setPos({ x, y, ready: true })
  }, [anchorRect])

  return createPortal(
    <div
      ref={ref}
      className="cite-tooltip"
      style={{
        position: 'fixed',
        left: pos.x,
        top: pos.y,
        opacity: pos.ready ? 1 : 0,
        pointerEvents: 'none',
        transition: 'opacity .15s ease',
      }}
    >
      {source?.label && <div className="cite-label">{source.label}</div>}
      <div className="cite-text">{source?.text || '(không có nội dung)'}</div>
      <div className="cite-hint">Nhấn để xem đầy đủ</div>
    </div>,
    document.body
  )
}

// ── Full-document modal ─────────────────────────────────────────────────────
function DocModal({ citeKey, source, onClose }) {
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      document.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="doc-modal-title"
    >
      <div className="modal-card" onMouseDown={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-left">
            <span className="cite-chip modal-cite-key">{citeKey}</span>
            <div>
              <p className="modal-eyebrow">Văn bản tham chiếu</p>
              <h2 id="doc-modal-title" className="modal-title">
                {source?.label || citeKey}
              </h2>
            </div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Đóng (Esc)">
            <X size={16} />
          </button>
        </div>

        <div className="modal-body">
          {source?.text
            ? <div className="modal-doc-text">{source.text}</div>
            : <p className="modal-empty">Không có nội dung chi tiết cho nguồn này.</p>
          }
        </div>

        <div className="modal-footer">
          <span className="modal-footer-hint">Nhấn Esc hoặc vùng tối để đóng</span>
          <button className="modal-footer-btn" onClick={onClose}>Đóng</button>
        </div>
      </div>
    </div>,
    document.body
  )
}

// ── MessageBubble ───────────────────────────────────────────────────────────
export default function MessageBubble({ message }) {
  const { role, text, sources = {} } = message
  const isUser = role === 'user'

  const [tooltip, setTooltip] = useState(null)  // { key, rect }
  const [modal, setModal]     = useState(null)   // { key }
  const closeModal = useCallback(() => setModal(null), [])

  // React synthetic events on the prose div catch clicks/hovers from inside
  // dangerouslySetInnerHTML — they bubble to the root where React intercepts.
  const handleClick = useCallback((e) => {
    const chip = e.target.closest('[data-cite-key]')
    if (!chip) return
    setTooltip(null)
    setModal({ key: chip.dataset.citeKey })
  }, [])

  const handleMouseOver = useCallback((e) => {
    const chip = e.target.closest('[data-cite-key]')
    setTooltip(chip
      ? { key: chip.dataset.citeKey, rect: chip.getBoundingClientRect() }
      : null
    )
  }, [])

  const handleMouseLeave = useCallback(() => setTooltip(null), [])

  /* ── User bubble ── */
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="msg-user">{text}</div>
      </div>
    )
  }

  /* ── Bot message ── */
  const html = marked.parse(injectCiteHTML(text))

  return (
    <>
      <div className="flex gap-3 items-start">
        <div className="bot-avatar" aria-hidden="true">AI</div>

        <div className="flex-1 min-w-0">
          {text ? (
            <div
              className="prose"
              dangerouslySetInnerHTML={{ __html: html }}
              onClick={handleClick}
              onMouseOver={handleMouseOver}
              onMouseLeave={handleMouseLeave}
            />
          ) : (
            <div className="loading-dots" aria-label="Đang trả lời…">
              <span /><span /><span />
            </div>
          )}
        </div>
      </div>

      {tooltip && (
        <CiteTooltip anchorRect={tooltip.rect} source={sources[tooltip.key]} />
      )}

      {modal && (
        <DocModal
          citeKey={modal.key}
          source={sources[modal.key]}
          onClose={closeModal}
        />
      )}
    </>
  )
}
