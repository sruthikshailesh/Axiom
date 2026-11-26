import { Link } from 'react-router-dom'

interface EmptyStateAction {
  label: string
  to?: string
  onClick?: () => void
}

interface EmptyStateProps {
  /** Short heading for the empty region. */
  title: string
  /** One sentence explaining what will appear here. */
  body?: string
  action?: EmptyStateAction
}

/** The one empty state used everywhere: heading, sentence, next step. */
function EmptyState({ title, body, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <p className="empty-state-title">{title}</p>
      {body ? <p className="empty-state-body">{body}</p> : null}
      {action ? (
        action.to ? (
          <Link className="button button-secondary empty-state-action" to={action.to}>
            {action.label}
          </Link>
        ) : (
          <button
            className="button button-secondary empty-state-action"
            type="button"
            onClick={action.onClick}
          >
            {action.label}
          </button>
        )
      ) : null}
    </div>
  )
}

export default EmptyState
