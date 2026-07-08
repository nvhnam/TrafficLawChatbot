/**
 * Async generator that reads an NDJSON stream from a fetch Response.
 * Each yielded value is a parsed JSON object (one frame per line).
 */
export async function* parseNDJSONStream(response) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() // keep the incomplete tail
    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed) {
        try {
          yield JSON.parse(trimmed)
        } catch {
          // skip malformed line
        }
      }
    }
  }

  // flush remainder
  if (buffer.trim()) {
    try { yield JSON.parse(buffer.trim()) } catch { /* ignore */ }
  }
}
