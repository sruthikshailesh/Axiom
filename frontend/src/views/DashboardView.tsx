import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  currentUser,
  dashboardSummary,
  errorMessage,
  getRun,
  listSources,
  startDemoRun,
  type DashboardSummary,
  type RunDetail,
  type SourceSummary,
} from '../api'
import { rememberRun } from '../lastRun'
import StatusBadge from '../components/StatusBadge'

const STATUS_ORDER = ['verified', 'conflict', 'uncertain', 'superseded'] as const

function formatWhen(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

interface AttentionItem {
  key: string
  title: string
  detail: string
  to: string
  linkLabel: string
  tone: 'conflict' | 'failed' | 'source'
}

function DashboardView() {
  const navigate = useNavigate()

  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [username, setUsername] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sources, setSources] = useState<SourceSummary[] | null>(null)
  const [details, setDetails] = useState<Record<number, RunDetail>>({})
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoError, setDemoError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    dashboardSummary()
      .then((data) => {
        if (cancelled) return
        setSummary(data)
        setError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setError(errorMessage(err))
      })
    currentUser()
      .then((user) => {
        if (!cancelled) setUsername(user.username)
      })
      .catch(() => {
        // The greeting falls back to a neutral salutation.
      })
    listSources()
      .then((list) => {
        if (!cancelled) setSources(list)
      })
      .catch(() => {
        if (!cancelled) setSources([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Conflicted runs and their error lines are only in the run detail, so the
  // dashboard reads the recent runs once there is something to look at.
  useEffect(() => {
    if (!summary) return
    if (summary.runs_with_conflict === 0 && summary.failed_run_count === 0) return

    let cancelled = false
    const ids = summary.recent_runs.map((run) => run.id)
    Promise.all(ids.map((id) => getRun(id).catch(() => null))).then((list) => {
      if (cancelled) return
      const map: Record<number, RunDetail> = {}
      for (const item of list) if (item) map[item.id] = item
      setDetails(map)
    })

    return () => {
      cancelled = true
    }
  }, [summary])

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

  const attention: AttentionItem[] = []
  if (summary) {
    for (const run of summary.recent_runs) {
      const detail = details[run.id]
      if (detail && detail.conflicts.length > 0) {
        attention.push({
          key: `conflict-${run.id}`,
          title: `Run #${run.id} has a conflict`,
          detail: run.question,
          to: `/runs/${run.id}`,
          linkLabel: 'Open report',
          tone: 'conflict',
        })
      }
    }
    for (const run of summary.recent_runs) {
      if (run.status !== 'failed') continue
      attention.push({
        key: `failed-${run.id}`,
        title: `Run #${run.id} failed`,
        detail: details[run.id]?.error ?? 'The run could not finish.',
        to: `/runs/${run.id}`,
        linkLabel: 'Open report',
        tone: 'failed',
      })
    }
  }
  for (const source of sources ?? []) {
    if (source.chunk_count > 0) continue
    attention.push({
      key: `empty-${source.id}`,
      title: `“${source.title}” has no text chunks`,
      detail: 'The upload stored no readable passages, so a run cannot use it.',
      to: '/sources',
      linkLabel: 'Open sources',
      tone: 'source',
    })
  }

  const counts = summary?.claim_status_counts
  const claimTotal = counts
    ? counts.verified + counts.conflict + counts.uncertain + counts.superseded
    : 0

  const untouched = summary !== null && summary.sources === 0 && summary.runs === 0

  const summaryLine = summary
    ? untouched
      ? 'No sources or runs yet. Start by uploading a document.'
      : `${summary.sources} ${summary.sources === 1 ? 'source' : 'sources'} and ${
          summary.runs
        } ${summary.runs === 1 ? 'run' : 'runs'}. Latest run: ${
          summary.latest_run_status ?? 'none'
        }.`
    : 'Loading your workspace…'

  return (
    <div className="dashboard">
      <section className="card command">
        <p className="page-eyebrow">Command center · Overview</p>
        <h1 className="page-title">Welcome back, {username ?? 'there'}</h1>
        <p className="page-desc command-line">{summaryLine}</p>
        <div className="command-actions">
          <Link className="button" to="/ask">
            Ask a question
          </Link>
          <Link className="button button-secondary" to="/sources">
            Upload documents
          </Link>
          <button
            className="button button-secondary"
            type="button"
            onClick={() => void onLoadDemo()}
            disabled={demoLoading}
          >
            {demoLoading ? 'Loading demo…' : 'Load demo'}
          </button>
        </div>
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

      <section className="stat-grid" aria-label="Summary">
        <div className="card stat">
          <p className="stat-label">Sources</p>
          <p className="stat-value">{summary ? summary.sources : '—'}</p>
          <p className="stat-note">Documents indexed</p>
        </div>
        <div className="card stat">
          <p className="stat-label">Runs</p>
          <p className="stat-value">{summary ? summary.runs : '—'}</p>
          <p className="stat-note">Questions asked</p>
        </div>
        <div className="card stat">
          <p className="stat-label">Runs with a conflict</p>
          <p className="stat-value">{summary ? summary.runs_with_conflict : '—'}</p>
          <p className="stat-note">Two documents disagree</p>
        </div>
        <div className="card stat">
          <p className="stat-label">Latest run</p>
          {summary?.latest_run ? (
            <>
              <p className="stat-value stat-value-badge">
                <StatusBadge status={summary.latest_run.status} kind="run" />
              </p>
              <p className="stat-note">{formatWhen(summary.latest_run.created_at)}</p>
            </>
          ) : (
            <>
              <p className="stat-value stat-value-small">—</p>
              <p className="stat-note">No runs yet.</p>
            </>
          )}
        </div>
      </section>

      <div className="dash-cols">
        <section className="card">
          <div className="card-head">
            <h2 className="card-title">Needs your attention</h2>
            <span className="muted small">{attention.length} items</span>
          </div>

          {attention.length === 0 ? (
            <p className="empty">Nothing needs attention right now.</p>
          ) : (
            <ul className="attention-list">
              {attention.map((item) => (
                <li className={`attention-item attention-${item.tone}`} key={item.key}>
                  <div className="attention-main">
                    <p className="attention-title">{item.title}</p>
                    <p className="muted small attention-detail">{item.detail}</p>
                  </div>
                  <Link className="link" to={item.to}>
                    {item.linkLabel}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <div className="card-head">
            <h2 className="card-title">Claim statuses</h2>
            <span className="muted small">All runs</span>
          </div>

          {claimTotal === 0 ? (
            <p className="empty">No claims yet.</p>
          ) : (
            <ul className="claim-counts">
              {STATUS_ORDER.map((status) => {
                const value = counts ? counts[status] : 0
                const share = claimTotal ? Math.round((value / claimTotal) * 100) : 0
                return (
                  <li className="claim-count-row" key={status}>
                    <StatusBadge status={status} />
                    <span className="claim-bar" aria-hidden="true">
                      <span
                        className={`claim-bar-fill claim-bar-${status}`}
                        style={{ width: `${share}%` }}
                      />
                    </span>
                    <span className="claim-count-value">
                      {value}
                      <span className="muted small"> · {share}%</span>
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <h2 className="card-title">Recent runs</h2>
          <span className="muted small">Last {summary?.recent_runs.length ?? 0}</span>
        </div>

        {summary === null && !error ? <p className="muted">Loading runs…</p> : null}

        {summary && summary.recent_runs.length === 0 ? (
          <p className="empty">
            No runs yet. Ask a question, or load the demo to see a full report.
          </p>
        ) : null}

        {summary && summary.recent_runs.length > 0 ? (
          <div className="table-scroll">
            <table className="runs-table">
              <thead>
                <tr>
                  <th scope="col">Question</th>
                  <th scope="col">Status</th>
                  <th scope="col">Time</th>
                  <th scope="col">Report</th>
                </tr>
              </thead>
              <tbody>
                {summary.recent_runs.map((run) => (
                  <tr key={run.id}>
                    <td className="runs-question">
                      <Link to={`/runs/${run.id}`}>{run.question}</Link>
                      {run.demo ? <span className="muted small"> · synthetic demo</span> : null}
                    </td>
                    <td>
                      <StatusBadge status={run.status} kind="run" />
                    </td>
                    <td className="muted small">{formatWhen(run.created_at)}</td>
                    <td>
                      <Link className="link" to={`/runs/${run.id}`}>
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  )
}

export default DashboardView
