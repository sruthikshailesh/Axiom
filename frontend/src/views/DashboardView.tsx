import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  dashboardSummary,
  errorMessage,
  startDemoRun,
  type DashboardSummary,
  type RecentRun,
} from '../api'
import { rememberRun } from '../lastRun'

function formatWhen(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

function StatusPill({ status }: { status: string }) {
  return <span className={`run-status run-status-${status}`}>{status}</span>
}

function DashboardView() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoError, setDemoError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    dashboardSummary()
      .then((data) => {
        if (!cancelled) {
          setSummary(data)
          setError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function onLoadDemo() {
    if (demoLoading) return

    setDemoLoading(true)
    setDemoError(null)
    try {
      const run = await startDemoRun()
      rememberRun(run.id)
      navigate(`/runs/${run.id}`)
    } catch (err) {
      setDemoError(errorMessage(err))
      setDemoLoading(false)
    }
  }

  const needsOnboarding = summary !== null && (summary.sources === 0 || summary.runs === 0)

  return (
    <div className="dashboard">
      <h2 className="panel-title">Dashboard</h2>
      <section className="quick-actions" aria-label="Quick actions">
        <Link className="button" to="/">
          Ask a question
        </Link>
        <Link className="button button-secondary" to="/sources">
          Upload a document
        </Link>
        <button
          className="button button-secondary"
          type="button"
          onClick={() => void onLoadDemo()}
          disabled={demoLoading}
        >
          {demoLoading ? 'Loading demo…' : 'Load the demo'}
        </button>
      </section>

      {error ? (
        <div className="alert alert-error" role="alert">
          {error}
        </div>
      ) : null}

      {demoError ? (
        <div className="alert alert-error" role="alert">
          {demoError}
        </div>
      ) : null}

      {needsOnboarding ? (
        <section className="panel onboarding">
          <h2 className="panel-title">Getting started</h2>
          <p className="muted">
            There is nothing to summarise yet. Upload a document, or load the synthetic
            demo, then ask a question. The <Link to="/guide">Guide</Link> walks through the
            three steps.
          </p>
        </section>
      ) : null}

      <section className="stat-grid" aria-label="Summary">
        <div className="stat">
          <p className="stat-label">Sources</p>
          <p className="stat-value">{summary ? summary.sources : '—'}</p>
        </div>
        <div className="stat">
          <p className="stat-label">Runs</p>
          <p className="stat-value">{summary ? summary.runs : '—'}</p>
        </div>
        <div className="stat stat-accent">
          <p className="stat-label">Runs with a conflict</p>
          <p className="stat-value">{summary ? summary.runs_with_conflict : '—'}</p>
        </div>
        <div className="stat">
          <p className="stat-label">Latest run</p>
          <p className="stat-value stat-value-small">
            {summary ? (summary.latest_run_status ?? 'none yet') : '—'}
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2 className="panel-title">Recent runs</h2>
          <span className="muted small">Last five</span>
        </div>

        {summary === null && !error ? <p className="muted">Loading runs…</p> : null}

        {summary && summary.recent_runs.length === 0 ? (
          <p className="empty">
            No runs yet. Ask a question, or load the demo from the actions above.
          </p>
        ) : null}

        {summary && summary.recent_runs.length > 0 ? (
          <ul className="run-list">
            {summary.recent_runs.map((run: RecentRun) => (
              <li className="run-row" key={run.id}>
                <div className="run-main">
                  <Link className="run-question" to={`/runs/${run.id}`}>
                    {run.question}
                  </Link>
                  <span className="muted small">
                    Run #{run.id} · {formatWhen(run.created_at)}
                    {run.demo ? ' · synthetic demo' : ''}
                  </span>
                </div>
                <div className="run-side">
                  <StatusPill status={run.status} />
                  <Link className="link" to={`/runs/${run.id}`}>
                    Open report
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  )
}

export default DashboardView
