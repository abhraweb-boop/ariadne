/**
 * Type->hue map (P9: <=3 hue families + neutrals; color encodes semantics
 * only). Values align with the app's dark theme surfaces; contrast-checked
 * against --background per DESIGN.md.
 */

export const NODE_TYPE_META: Record<
  string,
  { label: string; color: string; glyph: string }
> = {
  session: { label: 'Session', color: 'var(--accent)', glyph: '◆' },
  file: { label: 'File', color: '#7aa2f7', glyph: '▤' },
  mem: { label: 'Memory', color: '#9ece6a', glyph: '●' },
  cmd: { label: 'Command', color: '#e0af68', glyph: '▸' },
  web: { label: 'Web', color: '#bb9af7', glyph: '◇' },
  url: { label: 'URL', color: '#bb9af7', glyph: '◇' },
  search: { label: 'Search', color: '#565f89', glyph: '○' }
}

export function metaFor(type: string): { label: string; color: string; glyph: string } {
  return (
    NODE_TYPE_META[type] ?? {
      label: type,
      color: 'var(--muted-foreground)',
      glyph: '·'
    }
  )
}
