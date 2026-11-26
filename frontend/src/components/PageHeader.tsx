import type { ReactNode } from 'react'

interface PageHeaderProps {
  /** Small letter-spaced capitals above the title, e.g. "REPORT". */
  eyebrow: string
  title: string
  description?: string
  /** Status badges and timestamps, rendered under the title. */
  meta?: ReactNode
}

/** The one h1 on the page lives here; every screen uses this header. */
function PageHeader({ eyebrow, title, description, meta }: PageHeaderProps) {
  return (
    <header className="page-head">
      <p className="page-eyebrow">{eyebrow}</p>
      <h1 className="page-title">{title}</h1>
      {description ? <p className="page-desc">{description}</p> : null}
      {meta ? <div className="page-meta">{meta}</div> : null}
    </header>
  )
}

export default PageHeader
