/** A status label. The text is always rendered: colour is never the only cue. */
function StatusBadge({ status, kind = 'claim' }: { status: string; kind?: 'claim' | 'run' }) {
  if (kind === 'run') {
    return <span className={`run-status run-status-${status}`}>{status}</span>
  }
  return <span className={`badge badge-${status}`}>{status}</span>
}

export default StatusBadge
