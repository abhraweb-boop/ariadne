/**
 * D1 — Files pane (port of Hermes desktop Files sidebar).
 *
 * Browse the workspace tree read-only (backend router), open files as
 * preview. Loading/error/empty states with retry (anti-slop).
 */

import { useCallback, useEffect, useState } from 'react'

import { get } from '../api'

interface FileEntry {
  name: string
  type: 'dir' | 'file'
  size: number
  mtime: number
}

export function FilesPane({ onClose }: { onClose: () => void }) {
  const [path, setPath] = useState('')
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<{ name: string; content: string; truncated: boolean } | null>(null)
  const [history, setHistory] = useState<string[]>([])

  const load = useCallback(async (dir: string) => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok: boolean; entries: FileEntry[] }>(
        `/api/ariadne/files/list?path=${encodeURIComponent(dir)}`
      )

      setEntries(r.entries)
      setPath(dir)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load('') }, [load])

  const openDir = useCallback((dir: string) => {
    setHistory((h) => [...h, path])
    setPreview(null)
    void load(dir)
  }, [path, load])

  const goUp = useCallback(() => {
    setHistory((h) => {
      const next = [...h]
      const prev = next.pop() ?? ''
      setPreview(null)
      void load(prev)

      return next
    })
  }, [load])

  const openFile = useCallback(async (name: string) => {
    const rel = path ? `${path}/${name}` : name

    try {
      const r = await get<{ ok: boolean; content: string; truncated: boolean }>(
        `/api/ariadne/files/read?path=${encodeURIComponent(rel)}`
      )

      setPreview({ name, content: r.content, truncated: r.truncated })
    } catch (e) {
      setError(String(e))
    }
  }, [path])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>📁 Files</span>
        {history.length > 0 && (
          <button onClick={goUp} style={ghostBtn}>↑ up</button>
        )}
        <button onClick={() => void load('')} style={ghostBtn}>↻</button>
        <span style={{ flex: 1, fontSize: 11, color: 'var(--muted-foreground, #888)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {path || '/'}
        </span>
        <button onClick={onClose} style={ghostBtn}>✕</button>
      </div>

      {preview ? (
        <div style={{ flex: 1, overflow: 'auto', padding: 12, minHeight: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <button onClick={() => setPreview(null)} style={ghostBtn}>← back</button>
            <span style={{ fontSize: 12, fontWeight: 600 }}>{preview.name}</span>
          </div>
          <pre
            style={{
              margin: 0,
              fontSize: 11,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'monospace',
              lineHeight: 1.5
            }}
          >
            {preview.content}
            {preview.truncated && '\n\n… truncated'}
          </pre>
        </div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
          {error && (
            <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
              {error}
              <button onClick={() => void load(path)} style={{ ...ghostBtn, marginLeft: 8 }}>Retry</button>
            </div>
          )}
          {!loading && !error && entries.length === 0 && (
            <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Empty directory.</div>
          )}
          {entries.map((e) => (
            <button
              key={e.name}
              onClick={() => (e.type === 'dir' ? openDir(e.name) : openFile(e.name))}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                width: '100%',
                padding: '6px 12px',
                textAlign: 'left',
                background: 'transparent',
                border: 'none',
                color: 'var(--foreground, #efefef)',
                cursor: 'pointer',
                fontSize: 12,
                fontFamily: 'inherit'
              }}
            >
              <span>{e.type === 'dir' ? '📂' : '📄'}</span>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.name}</span>
              {e.type === 'file' && (
                <span style={{ fontSize: 10, color: 'var(--muted-foreground, #888)', fontVariantNumeric: 'tabular-nums' }}>
                  {(e.size / 1024).toFixed(1)} KB
                </span>
              )}
            </button>
          ))}
        </div>
      )}
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
