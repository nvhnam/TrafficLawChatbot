import { create } from 'zustand'

let _msgId = 0
const nextId = () => ++_msgId

export const useChatStore = create((set, get) => ({
  messages: [],      // [{ id, role: 'user'|'bot', text, sources }]
  sources: {},       // current citation registry from last bot frame
  streaming: false,

  addUserMessage(text) {
    const msg = { id: nextId(), role: 'user', text, sources: {} }
    set(s => ({ messages: [...s.messages, msg] }))
    return msg.id
  },

  addBotMessage(text = '', sources = {}) {
    const msg = { id: nextId(), role: 'bot', text, sources }
    set(s => ({ messages: [...s.messages, msg] }))
    return msg.id
  },

  appendToken(id, token) {
    set(s => ({
      messages: s.messages.map(m =>
        m.id === id ? { ...m, text: m.text + token } : m
      ),
    }))
  },

  setSources(id, sources) {
    set(s => ({
      sources,
      messages: s.messages.map(m => (m.id === id ? { ...m, sources } : m)),
    }))
  },

  setStreaming(v) {
    set({ streaming: v })
  },

  clearMessages() {
    set({ messages: [], sources: {} })
  },

  getHistory() {
    return get()
      .messages.slice(-6)
      .map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', text: m.text }))
  },
}))
