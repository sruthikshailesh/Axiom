import type { ReactNode } from 'react'

/** Every shell icon shares one stroke weight and inherits the text colour. */
function Glyph({ size = 18, children }: { size?: number; children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

type IconProps = { size?: number }

/** The A-with-gold-apex mark, the same drawing as the sign-in page. */
export function AxiomMark({ size = 26 }: IconProps) {
  return (
    <svg
      width={size}
      height={Math.round((size * 36) / 32)}
      viewBox="0 0 32 36"
      aria-hidden="true"
      focusable="false"
      className="side-mark-svg"
    >
      <line x1="4" y1="32" x2="16" y2="5" />
      <line x1="16" y1="5" x2="28" y2="32" />
      <line x1="9.6" y1="23" x2="22.4" y2="23" />
      <circle cx="16" cy="5" r="2.6" />
    </svg>
  )
}

export function SearchIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <circle cx="11" cy="11" r="6.5" />
      <line x1="16" y1="16" x2="21" y2="21" />
    </Glyph>
  )
}

export function PanelIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <line x1="9" y1="4" x2="9" y2="20" />
      <path d="M14.5 10 12 12.5l2.5 2.5" />
    </Glyph>
  )
}

export function UploadIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <path d="M12 16V4" />
      <path d="m7.5 8 4.5-4 4.5 4" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </Glyph>
  )
}

export function SparkIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <path d="M12 3.5 13.8 9l5.5 1.8-5.5 1.8L12 18.2l-1.8-5.6L4.7 10.8 10.2 9Z" />
      <path d="M18.5 16.5 19.2 18.6 21.3 19.3 19.2 20 18.5 22.1 17.8 20 15.7 19.3 17.8 18.6Z" />
    </Glyph>
  )
}

export function PlayIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <rect x="3" y="4.5" width="18" height="15" rx="2" />
      <path d="M10 9.2 15 12l-5 2.8Z" />
    </Glyph>
  )
}

export function GridIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.4" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.4" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.4" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.4" />
    </Glyph>
  )
}

export function DocIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <path d="M13.5 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9Z" />
      <path d="M13.5 3.5V9H19" />
      <line x1="8.5" y1="13" x2="15.5" y2="13" />
      <line x1="8.5" y1="16.5" x2="13" y2="16.5" />
    </Glyph>
  )
}

export function BookIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H10a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H5.5A1.5 1.5 0 0 1 4 15.5Z" />
      <path d="M20 5.5A1.5 1.5 0 0 0 18.5 4H14a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h4.5A1.5 1.5 0 0 0 20 15.5Z" />
    </Glyph>
  )
}

export function ChevronIcon({ size = 14, open = false }: IconProps & { open?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={open ? 'chevron chevron-open' : 'chevron'}
    >
      <path d="m6 9.5 6 6 6-6" />
    </svg>
  )
}

export function MenuIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="17" x2="20" y2="17" />
    </Glyph>
  )
}

export function AlertIcon({ size = 16 }: IconProps) {
  return (
    <Glyph size={size}>
      <path d="M12 4 21 19H3Z" />
      <line x1="12" y1="10" x2="12" y2="14" />
      <circle cx="12" cy="16.6" r="0.5" />
    </Glyph>
  )
}

export function CloseIcon({ size }: IconProps) {
  return (
    <Glyph size={size}>
      <line x1="6" y1="6" x2="18" y2="18" />
      <line x1="18" y1="6" x2="6" y2="18" />
    </Glyph>
  )
}
