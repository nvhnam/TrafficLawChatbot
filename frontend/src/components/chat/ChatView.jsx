import { useRef, useEffect, useState } from 'react'
import { useChatStore } from '../../stores/chatStore'
import { streamChat } from '../../lib/api'
import MessageBubble from './MessageBubble'
import SourcesPanel from './SourcesPanel'
import ImageUpload from './ImageUpload'
import { Send, RefreshCw } from '../icons'

const SUGGESTED = [
  'Tốc độ tối đa trong khu dân cư là bao nhiêu?',
  'Mức phạt khi vượt đèn đỏ là bao nhiêu?',
  'Điều kiện để được cấp bằng lái xe hạng B2?',
  'Quy định về nồng độ cồn khi điều khiển xe?',
]

export default function ChatView() {
  const [input, setInput] = useState('')
  const [image, setImage] = useState(null)
  const [focused, setFocused] = useState(false)
  const endRef = useRef(null)
  const textareaRef = useRef(null)

  const {
    messages, streaming,
    addUserMessage, addBotMessage, appendToken,
    setSources, setStreaming, clearMessages, getHistory,
  } = useChatStore()

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send(overrideText) {
    const q = (overrideText ?? input).trim()
    if (!q || streaming) return

    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    const history = getHistory()
    addUserMessage(q)
    const botId = addBotMessage('', {})
    setStreaming(true)

    try {
      for await (const frame of streamChat(q, history, image)) {
        if (frame.type === 'sources') setSources(botId, frame.data)
        else if (frame.type === 'token') appendToken(botId, frame.data)
        else if (frame.type === 'error') appendToken(botId, `\n\n*Lỗi: ${frame.data}*`)
      }
    } catch {
      appendToken(botId, `\n\n*Kết nối bị gián đoạn.*`)
    } finally {
      setStreaming(false)
      setImage(null)
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const canSend = !!input.trim() && !streaming

  return (
    <div className="flex flex-col h-full">

      {/* ── Message list ──────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto min-h-0 chat-scroll">
        {messages.length === 0 ? (
          <div className="empty-state">
            <div className="empty-logo">
              <span>VN</span>
              <span className="empty-logo-sub">Traffic Law AI</span>
            </div>
            <p className="empty-sub">Hỏi về luật giao thông đường bộ Việt Nam</p>
            <div className="suggested-grid">
              {SUGGESTED.map(s => (
                <button
                  key={s}
                  className="suggested-btn"
                  onClick={() => send(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="message-list">
            {messages.map(msg => (
              <div key={msg.id} className="message-row">
                <MessageBubble message={msg} />
                {msg.role === 'bot' && Object.keys(msg.sources || {}).length > 0 && (
                  <div className="sources-offset">
                    <SourcesPanel sources={msg.sources} />
                  </div>
                )}
              </div>
            ))}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* ── Input bar ─────────────────────────────────────────────── */}
      <div className="input-bar-wrap">
        <div
          className="input-bar"
          style={{ borderColor: focused ? 'var(--accent)' : 'var(--border)' }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
        >
          <ImageUpload image={image} onChange={setImage} />

          <textarea
            ref={textareaRef}
            rows={1}
            className="input-textarea"
            placeholder="Hỏi về luật giao thông… (Enter để gửi)"
            value={input}
            onChange={e => {
              setInput(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px'
            }}
            onKeyDown={onKeyDown}
          />

          <div className="input-actions">
            {messages.length > 0 && !streaming && (
              <button
                className="icon-btn"
                onClick={clearMessages}
                title="Xóa cuộc trò chuyện"
              >
                <RefreshCw size={15} />
              </button>
            )}
            <button
              className={`send-btn${canSend ? ' send-btn--active' : ''}`}
              onClick={() => send()}
              disabled={!canSend}
              title="Gửi (Enter)"
            >
              <Send size={14} />
            </button>
          </div>
        </div>

        <p className="input-hint">
          Enter để gửi&nbsp;&nbsp;·&nbsp;&nbsp;Shift + Enter xuống dòng
        </p>
      </div>
    </div>
  )
}
