import { useState, useRef, useCallback } from 'react'
import { computePosition, flip, shift, offset } from '@floating-ui/dom'

export default function CitationChip({ id, source }) {
  const [visible, setVisible] = useState(false)
  const [coords, setCoords] = useState({ x: 0, y: 0 })
  const chipRef = useRef(null)
  const tooltipRef = useRef(null)

  const show = useCallback(async () => {
    setVisible(true)
    if (chipRef.current && tooltipRef.current) {
      const { x, y } = await computePosition(chipRef.current, tooltipRef.current, {
        placement: 'top',
        middleware: [offset(6), flip(), shift({ padding: 8 })],
      })
      setCoords({ x, y })
    }
  }, [])

  const hide = useCallback(() => setVisible(false), [])

  if (!source) {
    return <span className="cite-chip opacity-50">{id}</span>
  }

  return (
    <>
      <span
        ref={chipRef}
        className="cite-chip"
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        tabIndex={0}
        role="button"
        aria-label={`Citation ${id}: ${source.label}`}
      >
        {id}
      </span>

      {/* Tooltip rendered via portal-style fixed positioning */}
      <div
        ref={tooltipRef}
        className="cite-tooltip"
        style={{
          left: coords.x,
          top: coords.y,
          opacity: visible ? 1 : 0,
          pointerEvents: visible ? 'auto' : 'none',
          transition: 'opacity .12s ease',
        }}
        role="tooltip"
      >
        {source.label && <div className="cite-label">{source.label}</div>}
        <div className="cite-text">{source.text || '(no text available)'}</div>
      </div>
    </>
  )
}
