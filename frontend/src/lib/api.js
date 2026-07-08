import { parseNDJSONStream } from './stream.js'

let _sessionId = null

function getSessionId() {
  if (!_sessionId) _sessionId = `session-${Date.now()}-${Math.random().toString(36).slice(2)}`
  return _sessionId
}

export function newSession() {
  _sessionId = `session-${Date.now()}-${Math.random().toString(36).slice(2)}`
  return _sessionId
}

/**
 * Async generator for chat streaming.
 * Yields NDJSON frames: { type: 'sources'|'token'|'done'|'error', data: ... }
 */
export async function* streamChat(question, history, imageBase64 = null) {
  const endpoint = imageBase64 ? '/answer_with_image_input' : '/chat_stream'
  const body = imageBase64
    ? { current_question: question, history, image: imageBase64 }
    : { current_question: question, history, session_id: getSessionId() }

  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    yield { type: 'error', data: `Server error: ${res.status}` }
    return
  }

  yield* parseNDJSONStream(res)
}

export async function fetchDocuments() {
  const res = await fetch('/get_system_stats')
  const json = await res.json()
  return json.data || { danh_sach_van_ban: [], tong_so_doan_van_ban: 0 }
}

export async function deleteDocument(name) {
  const res = await fetch('/delete_document', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_name: name }),
  })
  return res.json()
}

export async function checkProgress() {
  const res = await fetch('/check_progress')
  const json = await res.json()
  return json.data || {}
}

export async function uploadFiles(formData) {
  const res = await fetch('/process_folder_and_build', {
    method: 'POST',
    body: formData,
  })
  return res.json()
}
