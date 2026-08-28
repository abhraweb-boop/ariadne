/**
 * P — ArtifactsPane: read-only preview of workspace artifacts.
 *
 * Lists the workspace root (via /api/ariadne/files/list) and previews a
 * selected artifact: text -> pre, images -> img, PDFs -> embed.
 */

import { useCallback, useEffect, useState } from 'react'

import { get } from '../api'

interface FileEntry {
  name: string
  path: string
  type?: string
  size?: number
}

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|svg|ico)$/i
const PDF_EXT = /\.pdf$/i

function isTextLike(name: string): boolean {
  return /\.(md|txt|json|yaml|yml|toml|py|js|ts|tsx|jsx|css|html|sql|sh|c|cpp|rs|go)$/i.test(name)
}

export function ArtifactsPane({ onClose }: { onClose: () => void }) {
  const [files, setFiles] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<FileEntry | null>(null)
  const [content, setContent] = useState('')
  const [reading, setReading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok?: boolean; path?: string; entries?: FileEntry[]; files?: FileEntry[] }>('/api/ariadne/files/list?path=')
      setFiles((r.entries ?? r.files ?? []).map((e) => ({
        name: e.name ?? '',
        path: e.name ?? '',
      })))
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const select = useCallback(async (f: FileEntry) => {
    setSelected(f)
    setContent('')

    if (!isTextLike(f.path)) {return}
    setReading(true)

    try {
      const r = await get<{ ok?: boolean; content?: string; text?: string }>(`/api/ariadne/files/read?path=${encodeURIComponent(f.path)}`)
      setContent(r.content ?? r.text ?? '')
    } catch (e) {
      setContent(`Failed: ${String(e)}`)
    } finally {
      setReading(false)
    }
  }, [])

  const readUrl = selected ? `/api/ariadne/files/read?path=${encodeURIComponent(selected.path)}` : ''

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>🖼 Artifacts</span>
        <button onClick={() => void load()} style={ghostBtn}>↻</button>
        <button aria-label="Close" onClick={onClose} style={{ ...ghostBtn, marginLeft: 'auto' }}>✕</button>
      </div>

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* File list */}
        <div style={{ width: 180, overflowY: 'auto', borderRight: '1px solid var(--border, #2a2a2a)', flexShrink: 0 }}>
          {loading && <div style={{ padding: 12, fontSize: 11, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
          {error && (
            <div style={{ padding: 12, fontSize: 11, color: '#f7768e' }}>
              {error} <button onClick={() => void load()} style={ghostBtn}>Retry</button>
            </div>
          )}
          {!loading && !error && files.length === 0 && (
            <div style={{ padding: 12, fontSize: 11, color: 'var(--muted-foreground, #888)' }}>No artifacts.</div>
          )}
          {files.map((f) => (
            <button
              key={f.path}
              onClick={() => void select(f)}
              style={{
                display: 'block',
                width: '100%',
                padding: '6px 10px',
                background: selected?.path === f.path ? 'color-mix(in srgb, var(--accent, #5e6ad2) 12%, transparent)' : 'transparent',
                border: 'none',
                borderBottom: '1px solid var(--border, #2a2a2a)',
                color: 'var(--foreground, #efefef)',
                cursor: 'pointer',
                textAlign: 'left',
                fontFamily: 'inherit',
                fontSize: 11,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}
            >
              {f.name}
            </button>
          ))}
        </div>

        {/* Preview */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 12, minWidth: 0 }}>
          {!selected && (
            <div style={{ fontSize: 12, color: 'var(--muted-foreground, #888)' }}>
              Select an artifact to preview. Text files render inline; images and PDFs embed.
            </div>
          )}
          {selected && isTextLike(selected.path) && (
            <pre style={{ fontSize: 11, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>
              {reading ? 'Reading…' : content || '(empty)'}
            </pre>
          )}
          {selected && IMAGE_EXT.test(selected.path) && (
            <img alt={selected.name} src={readUrl} style={{ maxWidth: '100%', borderRadius: 6 }} />
          )}
          {selected && PDF_EXT.test(selected.path) && (
            <embed src={readUrl} style={{ width: '100%', height: '70vh', border: '1px solid var(--border, #2a2a2a)', borderRadius: 6 }} type="application/pdf" />
          )}
          {selected && !isTextLike(selected.path) && !IMAGE_EXT.test(selected.path) && !PDF_EXT.test(selected.path) && (
            <div style={{ fontSize: 12, color: 'var(--muted-foreground, #888)' }}>
              Preview not available for this type. Open it in the Files pane.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const ghostBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--border, #2a2a2a)',
  borderRadius: 4,
  color: 'var(--foreground, #efefef)',
  cursor: 'pointer',
  fontSize: 11,
  fontFamily: 'inherit',
  padding: '2px 6px'
}