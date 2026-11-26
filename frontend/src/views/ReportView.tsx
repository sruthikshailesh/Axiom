import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { errorMessage, getRun, type Claim, type RunDetail } from '../api'

const ACTIVE_STATUSES = ['queued', 'researching', 'extracting', 'verifying']
const STEPS = ['researching', 'extracting', 'verifying', 'done']

function currentStep(status: string): number {
  if (status === 'completed') return 3
  return STEPS.indexOf(status) // -1 while queued
}

function StatusBadge({ status }: { status: Claim['status'] }) {
  return <span className={`badge badge-${status}`}>{status}</span>
}

function ClaimItem({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false)
  const percent = Math.round(claim.confidence * 100)

  return (
    <li className={`claim claim-${claim.status}`}>
      <button
        className="claim-head"
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="claim-toggle" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
        <span className="claim-text">{claim.text}</span>
        <span className="claim-meta">
          <StatusBadge status={claim.status} />
          <span className="confidence" title="Confidence">
            {percent}%
          </span>
        </span>
      </button>

      {claim.uncertainty_note ? (
        <p className="claim-note">{claim.uncertainty_note}</p>
      ) : null}

      {open ? (
        <div className="claim-body">
          <dl className="claim-facts">
            {claim.claim_date ? (
              <div>
                <dt>Claim date</dt>
                <dd>{claim.claim_date}</dd>
              </div>
            ) : null}
            {claim.owner ? (
              <div>
                <dt>Owner</dt>
                <dd>{claim.owner}</dd>
              </div>
            ) : null}
          </dl>

          {claim.evidence.length ? (
            claim.evidence.map((evidence) => (
              <div className="evidence" key={`${evidence.chunk_id}-${evidence.quote}`}>
                <p className="evidence-source">
                  {evidence.source_title}
                  <span className="muted small"> · chunk {evidence.chunk_id}</span>
                </p>
                <blockquote className="quote">{evidence.quote}</blockquote>
              </div>
            ))
          ) : (
            <p className="muted">No evidence stored for this claim.</p>
          )}
        </div>
      ) : null}
    </li>
  )
}

function ReportView() {
  const { id } = useParams()
  const [run, setRun] = useState<RunDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const runId = Number(id)
    if (!Number.isInteger(runId) || runId <= 0) {
      setLoading(false)
      setError('That run id is not valid.')
      return
    }

    let cancelled = false
    let timer: number | undefined

    async function poll() {
      try {
        const detail = await getRun(runId)
        if (cancelled) return
        setRun(detail)
        setError(null)
        setLoading(false)
        if (ACTIVE_STATUSES.includes(detail.status)) {
          timer = window.setTimeout(poll, 1000)
        }
      } catch (err) {
        if (cancelled) return
        setError(errorMessage(err))
        setLoading(false)
      }
    }

    void poll()
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [id])

  if (loading) {
    return (
      <section className="panel">
        <p className="muted">Loading run…</p>
      </section>
    )
  }

  if (!run) {
    return (
      <section className="panel">
        <h2 className="panel-title">Run unavailable</h2>
        <div className="alert alert-error" role="alert">
          {error ?? 'Run not found.'}
        </div>
        <Link className="link" to="/">
          Back to the query view
        </Link>
      </section>
    )
  }

  const running = ACTIVE_STATUSES.includes(run.status)
  const step = currentStep(run.status)
  const claimsById = new Map(run.claims.map((claim) => [claim.id, claim]))

  return (
    <div className="report">
      {run.demo ? (
        <div className="alert alert-demo" role="note">
          This run uses synthetic demo data for a fictional project. It is not real
          project information.
        </div>
      ) : null}

      <section className="panel">
        <h2 className="panel-title">{run.question}</h2>
        <p className="muted small">Run #{run.id}</p>

        {running ? (
          <p className="muted">
            {run.status === 'queued' ? 'Queued — waiting to start.' : `Working: ${run.status}.`}
          </p>
        ) : null}

        <ol className="steps" aria-label="Pipeline progress">
          {STEPS.map((label, index) => {
            const state =
              run.status === 'completed'
                ? 'done'
                : index < step
                  ? 'done'
                  : index === step
                    ? 'current'
                    : 'pending'
            return (
              <li
                key={label}
                className={`step step-${state}`}
                aria-current={index === step ? 'step' : undefined}
              >
                <span className="step-dot" aria-hidden="true" />
                {label}
              </li>
            )
          })}
        </ol>

        {error ? (
          <div className="alert alert-warning" role="status">
            {error}
          </div>
        ) : null}

        {run.status === 'failed' ? (
          <div className="alert alert-error" role="alert">
            <strong>The run could not finish.</strong>
            <p>{run.error ?? 'No error message was recorded.'}</p>
            <Link className="link" to="/">
              Back to the query view
            </Link>
          </div>
        ) : null}
      </section>

      {run.status === 'completed' ? (
        <>
          <section className="panel">
            <h3 className="panel-title">Claims ({run.claims.length})</h3>
            {run.claims.length === 0 ? (
              <p className="empty">
                No claims were extracted for this question.
                <span className="muted"> “{run.question}”</span> Try a broader question, and
                check the Sources page that your documents were uploaded.
              </p>
            ) : (
              <ul className="claims">
                {run.claims.map((claim) => (
                  <ClaimItem claim={claim} key={claim.id} />
                ))}
              </ul>
            )}
          </section>

          <section className="panel">
            <h3 className="panel-title">Supersessions ({run.supersessions.length})</h3>
            {run.supersessions.length === 0 ? (
              <p className="empty">
                No claim supersedes another in this run. Read the claims above; nothing needs
                resolving here.
              </p>
            ) : (
              run.supersessions.map((supersession) => (
                <div className="pair" key={`${supersession.old_claim_id}-${supersession.new_claim_id}`}>
                  <div className="pair-side">
                    <p className="pair-label">Old claim</p>
                    <p>{claimsById.get(supersession.old_claim_id)?.text ?? `Claim #${supersession.old_claim_id}`}</p>
                  </div>
                  <div className="pair-side">
                    <p className="pair-label">New claim</p>
                    <p>{claimsById.get(supersession.new_claim_id)?.text ?? `Claim #${supersession.new_claim_id}`}</p>
                  </div>
                  <p className="pair-reason">{supersession.reason}</p>
                </div>
              ))
            )}
          </section>

          <section className="panel">
            <h3 className="panel-title">Conflicts ({run.conflicts.length})</h3>
            {run.conflicts.length === 0 ? (
              <p className="empty">
                No conflicting claims in this run. Read the claims above; nothing needs
                resolving here.
              </p>
            ) : (
              run.conflicts.map((conflict) => (
                <div className="pair" key={`${conflict.claim_a_id}-${conflict.claim_b_id}`}>
                  <div className="pair-side">
                    <p className="pair-label">Claim A</p>
                    <p>{claimsById.get(conflict.claim_a_id)?.text ?? `Claim #${conflict.claim_a_id}`}</p>
                  </div>
                  <div className="pair-side">
                    <p className="pair-label">Claim B</p>
                    <p>{claimsById.get(conflict.claim_b_id)?.text ?? `Claim #${conflict.claim_b_id}`}</p>
                  </div>
                  <p className="pair-reason">{conflict.reason}</p>
                </div>
              ))
            )}
          </section>
        </>
      ) : null}
    </div>
  )
}

export default ReportView
