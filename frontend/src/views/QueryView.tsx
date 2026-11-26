import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorMessage, startDemoRun, startRun } from '../api'
import { rememberRun } from '../lastRun'
import PageHeader from '../components/PageHeader'

function QueryView() {
  const [question, setQuestion] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoError, setDemoError] = useState<string | null>(null)
  const navigate = useNavigate()

  const canSubmit = question.trim().length > 0 && !submitting

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit) return

    setSubmitting(true)
    setError(null)
    try {
      const run = await startRun(question.trim())
      rememberRun(run.id)
      navigate(`/runs/${run.id}`)
    } catch (err) {
      setError(errorMessage(err))
      setSubmitting(false)
    }
  }

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

  return (
    <div className="ask">
      <PageHeader
        eyebrow="Ask"
        title="Ask a question"
        description="AXIOM searches your sources, extracts claims, and checks each one against its evidence."
      />

      <section className="card">
      <form className="query-form" onSubmit={onSubmit}>
        <label className="field">
          <span className="field-label">Question</span>
          <input
            className="input"
            type="text"
            value={question}
            placeholder="What is the ionosphere?"
            onChange={(event) => setQuestion(event.target.value)}
            disabled={submitting}
          />
        </label>
        <div className="form-actions">
          <button className="button" type="submit" disabled={!canSubmit}>
            {submitting ? 'Starting…' : 'Submit'}
          </button>
          <span className="demo-slot">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => void onLoadDemo()}
              disabled={demoLoading}
              title="Load four synthetic demo documents and run the demo question"
            >
              {demoLoading ? 'Loading demo…' : 'Load demo'}
            </button>
            <span className="muted small">
              Four synthetic documents about a fictional project.
            </span>
          </span>
        </div>
      </form>

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
      </section>
    </div>
  )
}

export default QueryView
