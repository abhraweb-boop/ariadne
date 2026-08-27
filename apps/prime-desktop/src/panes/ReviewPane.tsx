/**
 * D3 — Review pane (git). Port of Hermes desktop Review sidebar.
 * Lists uncommitted changes, shows diffs, stage/unstage, file diff.
 */

import { useCallback, useEffect, useState } from 'react'

import { get } from '../api'

interface ReviewFile {
  path: string
  status: string
  staged: boolean
  hunks: number
  insertions: number
  deletions: number
}

export function ReviewPane({ onClose }: { onClose: () => void }) {
  const [files, setFiles] = useState<ReviewFile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [diffContent, setDiffContent] = useState<string | null>(null)
  const [diffFile, setDiffFile] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok: boolean; files?: ReviewFile[] }>('/api/git/review/list?path=.')
      setFiles(r.files ?? [])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const showDiff = useCallback(async (file: string) => {
    try {
      const r = await get<{ diff: string }>(`/api/git/file-diff?path=.&file=${encodeURIComponent(file)}`)
      setDiffContent(r.diff)
      setDiffFile(file)
    } catch (e) {
      setDiffContent(`Error: ${String(e)}`)
      setDiffFile(file)
    }
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>🔍 Review</span>
        <button onClick={() => void load()} style={ghostBtn}>↻</button>
        <button aria-label="Close" onClick={onClose} style={ghostBtn}></button>
      </div>

      {diffContent !== null ? (
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', fontSize: 12 }}>
            <button onClick={() => { setDiffContent(null); setDiffFile(null) }} style={ghostBtn}>← back</button>
            <span style={{ fontWeight: 600 }}>{diffFile}</span>
          </div>
          <pre
            style={{
              margin: 0,
              padding: 12,
              fontSize: 11,
              fontFamily: 'monospace',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              lineHeight: 1.5
            }}
          >
            {diffContent}
          </pre>
        </div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
          {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
          {error && (
            <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
              {error} <button onClick={() => void load()} style={ghostBtn}>Retry</button>
            </div>
          )}
          {!loading && !error && files.length === 0 && (
            <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>
              No uncommitted changes.
            </div>
          )}
          {files.map((f) => (
            <div
              key={f.path}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                borderBottom: '1px solid var(--border, #2a2a2a)',
                fontSize: 12
              }}
            >
              <span
                style={{
                  fontWeight: 700,
                  fontSize: 10,
                  minWidth: 20,
                  color: f.status === 'M' ? '#e0af68' : f.status === 'A' ? '#9ece6a' : '#f7768e'
                }}
              >
                {f.status}
              </span>
              <button
                onClick={() => showDiff(f.path)}
                style={{
                  flex: 1,
                  textAlign: 'left',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--foreground, #efefef)',
                  cursor: 'pointer',
                  fontSize: 12,
                  fontFamily: 'inherit'
                }}
              >
                {f.path}
              </button>
              {f.insertions > 0 && (
                <span style={{ color: '#9ece6a', fontSize: 10, fontVariantNumeric: 'tabular-nums' }}>
                  +{f.insertions}
                </span>
              )}
              {f.deletions > 0 && (
                <span style={{ color: '#f7768e', fontSize: 10, fontVariantNumeric: 'tabular-nums' }}>
                  -{f.deletions}
                </span>
              )}
            </div>
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