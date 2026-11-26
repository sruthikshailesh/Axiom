import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { errorMessage, login, register } from '../api'
import { getToken, setToken } from '../session'

const WORKFLOW = ['UPLOAD', 'RESEARCH', 'EXTRACT', 'VERIFY', 'REPORT']

type Mode = 'signin' | 'create'

const GLYPHS = '{}[]/\\<>0123456789#|—·'.split('')

interface DriftNode {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
}

interface Glyph {
  x: number
  y: number
  size: number
  alpha: number
  char: string
  drift: number
}

function seedNodes(width: number, height: number): DriftNode[] {
  const count = Math.min(44, Math.max(16, Math.round((width * height) / 30000)))
  return Array.from({ length: count }, () => {
    // A fixed speed per node (0.18-0.24 px per frame) so every node visibly
    // drifts instead of some sitting still at a near-zero velocity.
    const angle = Math.random() * Math.PI * 2
    const speed = 0.18 + Math.random() * 0.06
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      radius: 1.1 + Math.random() * 1.5,
    }
  })
}

function seedGlyphs(width: number, height: number): Glyph[] {
  const count = Math.min(26, Math.max(10, Math.round((width * height) / 42000)))
  return Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    size: 11 + Math.random() * 9,
    alpha: 0.04 + Math.random() * 0.07,
    char: GLYPHS[Math.floor(Math.random() * GLYPHS.length)],
    drift: 0.03 + Math.random() * 0.08,
  }))
}

/**
 * The left column's background: faint dusty-purple nodes with thin edges, plus a
 * few drifting document-like glyphs. It draws one still frame while the page is
 * hidden, under `prefers-reduced-motion: reduce`, or when the caller asks for a
 * still frame; in every one of those cases the animation loop is never started.
 */
function NodeField({ still }: { still: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const node = canvasRef.current
    if (!node) return
    const painter = node.getContext('2d')
    if (!painter) return

    // Explicit types so the nested drawing helpers keep the narrowed values.
    const canvas: HTMLCanvasElement = node
    const context: CanvasRenderingContext2D = painter
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')

    let nodes: DriftNode[] = []
    let glyphs: Glyph[] = []
    let frame: number | null = null
    let width = 0
    let height = 0

    function measure() {
      const rect = canvas.getBoundingClientRect()
      width = Math.max(1, Math.round(rect.width))
      height = Math.max(1, Math.round(rect.height))
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    function draw() {
      context.clearRect(0, 0, width, height)

      const reach = Math.min(160, Math.max(96, width / 5))
      context.lineWidth = 1
      for (let i = 0; i < nodes.length; i += 1) {
        const a = nodes[i]
        for (let j = i + 1; j < nodes.length; j += 1) {
          const b = nodes[j]
          const dx = a.x - b.x
          const dy = a.y - b.y
          const distance = Math.hypot(dx, dy)
          if (distance > reach) continue
          // Fainter as the two nodes drift apart.
          const alpha = 0.2 * (1 - distance / reach)
          context.strokeStyle = `rgba(139, 122, 168, ${alpha.toFixed(3)})`
          context.beginPath()
          context.moveTo(a.x, a.y)
          context.lineTo(b.x, b.y)
          context.stroke()
        }
      }

      context.fillStyle = 'rgba(139, 122, 168, 0.42)'
      for (const point of nodes) {
        context.beginPath()
        context.arc(point.x, point.y, point.radius, 0, Math.PI * 2)
        context.fill()
      }

      context.textBaseline = 'middle'
      for (const glyph of glyphs) {
        context.font = `${glyph.size}px "Space Grotesk", ui-monospace, monospace`
        context.fillStyle = `rgba(139, 122, 168, ${glyph.alpha.toFixed(3)})`
        context.fillText(glyph.char, glyph.x, glyph.y)
      }
    }

    function step() {
      for (const point of nodes) {
        point.x += point.vx
        point.y += point.vy
        // Wrap at the edges so the drift never stalls against a boundary.
        if (point.x < 0) point.x = width
        if (point.x > width) point.x = 0
        if (point.y < 0) point.y = height
        if (point.y > height) point.y = 0
      }
      for (const glyph of glyphs) {
        glyph.y -= glyph.drift
        if (glyph.y < -20) {
          glyph.y = height + 20
          glyph.x = Math.random() * width
          glyph.char = GLYPHS[Math.floor(Math.random() * GLYPHS.length)]
        }
      }
      draw()
      frame = window.requestAnimationFrame(step)
    }

    function stop() {
      if (frame !== null) {
        window.cancelAnimationFrame(frame)
        frame = null
      }
    }

    function restart() {
      stop()
      if (still || motionQuery.matches || document.hidden) {
        draw()
        return
      }
      frame = window.requestAnimationFrame(step)
    }

    function onResize() {
      measure()
      nodes = seedNodes(width, height)
      glyphs = seedGlyphs(width, height)
      restart()
    }

    measure()
    nodes = seedNodes(width, height)
    glyphs = seedGlyphs(width, height)
    restart()

    window.addEventListener('resize', onResize)
    document.addEventListener('visibilitychange', restart)
    motionQuery.addEventListener('change', restart)

    return () => {
      stop()
      window.removeEventListener('resize', onResize)
      document.removeEventListener('visibilitychange', restart)
      motionQuery.removeEventListener('change', restart)
    }
  }, [still])

  return <canvas ref={canvasRef} className="auth-canvas" aria-hidden="true" />
}

function AxiomMark() {
  return (
    <svg className="auth-mark" viewBox="0 0 32 36" width="30" height="34" aria-hidden="true">
      <line x1="4" y1="32" x2="16" y2="5" />
      <line x1="16" y1="5" x2="28" y2="32" />
      <line x1="9.6" y1="23" x2="22.4" y2="23" />
      <circle cx="16" cy="5" r="2.6" />
    </svg>
  )
}

function WarningTriangle() {
  return (
    <svg className="auth-status-icon" viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
      <path d="M10 2.8 18 17H2Z" />
      <line x1="10" y1="8" x2="10" y2="12" />
      <circle cx="10" cy="14.5" r="0.85" />
    </svg>
  )
}

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg
      className="auth-eye-icon"
      viewBox="0 0 24 24"
      width="19"
      height="19"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="2.9" />
      {open ? null : <line x1="4.5" y1="19.5" x2="19.5" y2="4.5" />}
    </svg>
  )
}

function SignInView() {
  const navigate = useNavigate()
  const location = useLocation()
  const stateMessage =
    (location.state as { message?: string } | null)?.message ?? null

  const [mode, setMode] = useState<Mode>('signin')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [revealPassword, setRevealPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [still, setStill] = useState(false)

  useEffect(() => {
    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    const sync = () => setStill(motionQuery.matches)
    sync()
    motionQuery.addEventListener('change', sync)
    return () => motionQuery.removeEventListener('change', sync)
  }, [])

  if (getToken()) return <Navigate to="/dashboard" replace />

  function switchMode(next: Mode) {
    if (busy || next === mode) return
    setMode(next)
    setError(null)
    setNotice(null)
    setPassword('')
    setConfirm('')
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return

    // The two passwords are compared here so a typo never reaches the backend.
    if (mode === 'create' && password !== confirm) {
      setNotice(null)
      setError('Passwords do not match.')
      return
    }

    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      if (mode === 'create') {
        const created = await register(username.trim(), password)
        setMode('signin')
        setUsername(created.username)
        setPassword('')
        setConfirm('')
        setNotice('Account created. Sign in to continue.')
        setBusy(false)
        return
      }

      const session = await login(username.trim(), password)
      setToken(session.token)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  const message = error ?? stateMessage
  const canSubmit =
    !busy &&
    Boolean(username.trim()) &&
    Boolean(password) &&
    (mode === 'signin' || Boolean(confirm))

  return (
    <div className="auth-page">
      <section className="auth-left">
        <NodeField still={still} />
        <div className="auth-left-inner">
          <header className="auth-brand">
            <div className="auth-brand-row">
              <AxiomMark />
              <span className="auth-wordmark">AXIOM</span>
            </div>
            <p className="auth-brand-sub">RESEARCH INTELLIGENCE</p>
          </header>

          <div className="auth-hero">
            <h1 className="auth-headline">
              Every claim <span className="auth-gold">traceable</span>.
              <br />
              Every conflict <span className="auth-gold">visible</span>.
            </h1>
            <p className="auth-subline">
              Evidence first. Conflicts shown. Uncertainty stated.
            </p>
          </div>

          <div className="auth-left-foot">
            <ol className="auth-flow" aria-label="How a run moves">
              {WORKFLOW.map((step, index) => (
                <li
                  key={step}
                  className={
                    index === 0 ? 'auth-flow-step auth-flow-step-active' : 'auth-flow-step'
                  }
                >
                  <span className="auth-flow-dot" aria-hidden="true" />
                  <span className="auth-flow-label">{step}</span>
                </li>
              ))}
            </ol>

            <div className="auth-status-bar">
              <span className="auth-status-tag">
                <WarningTriangle />
                <span>CONFLICT</span>
              </span>
              <span className="auth-status-rule" aria-hidden="true" />
              <p className="auth-status-text">
                Two documents disagree, or a newer record replaces an older one.
              </p>
            </div>
            <p className="auth-status-legend">
              Statuses: verified, conflict, uncertain, superseded.
            </p>
          </div>
        </div>
      </section>

      <section className="auth-right">
        <div className="auth-card">
          <div className="auth-tabs" role="tablist" aria-label="Account">
            <button
              id="auth-tab-signin"
              className="auth-tab"
              type="button"
              role="tab"
              aria-selected={mode === 'signin'}
              aria-controls="auth-panel"
              onClick={() => switchMode('signin')}
              disabled={busy}
            >
              Sign in
            </button>
            <button
              id="auth-tab-create"
              className="auth-tab"
              type="button"
              role="tab"
              aria-selected={mode === 'create'}
              aria-controls="auth-panel"
              onClick={() => switchMode('create')}
              disabled={busy}
            >
              Create account
            </button>
          </div>

          <form
            id="auth-panel"
            className="auth-form"
            role="tabpanel"
            aria-labelledby={mode === 'create' ? 'auth-tab-create' : 'auth-tab-signin'}
            onSubmit={onSubmit}
          >
            <div className="auth-field">
              <label className="auth-label" htmlFor="auth-username">
                Username
              </label>
              <input
                id="auth-username"
                className="auth-input"
                type="text"
                autoComplete="username"
                placeholder="Your username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                disabled={busy}
                required
              />
            </div>

            <div className="auth-field">
              <label className="auth-label" htmlFor="auth-password">
                Password
              </label>
              <div className="auth-password-row">
                <input
                  id="auth-password"
                  className="auth-input"
                  type={revealPassword ? 'text' : 'password'}
                  autoComplete={mode === 'create' ? 'new-password' : 'current-password'}
                  placeholder={mode === 'create' ? 'At least 8 characters' : 'Your password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={busy}
                  required
                />
                <button
                  className="auth-eye"
                  type="button"
                  aria-label={revealPassword ? 'Hide password' : 'Show password'}
                  onClick={() => setRevealPassword((current) => !current)}
                  disabled={busy}
                >
                  <EyeIcon open={!revealPassword} />
                </button>
              </div>
            </div>

            {mode === 'create' ? (
              <div className="auth-field">
                <label className="auth-label" htmlFor="auth-confirm">
                  Confirm password
                </label>
                <input
                  id="auth-confirm"
                  className="auth-input"
                  type={revealPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Repeat your password"
                  value={confirm}
                  onChange={(event) => setConfirm(event.target.value)}
                  disabled={busy}
                  required
                />
              </div>
            ) : null}

            <button className="auth-submit" type="submit" disabled={!canSubmit}>
              {mode === 'create'
                ? busy
                  ? 'Creating account…'
                  : 'Create account'
                : busy
                  ? 'Signing in…'
                  : 'Sign in'}
            </button>
          </form>

          {message ? (
            <p className="auth-error" role="alert">
              {message}
            </p>
          ) : null}

          {notice ? (
            <p className="auth-notice" role="status">
              {notice}
            </p>
          ) : null}

          <p className="auth-card-foot">
            Accounts are stored locally. Not production authentication.
          </p>
        </div>
      </section>
    </div>
  )
}

export default SignInView
