import { useEffect, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { errorMessage, login } from '../api'
import { getToken, setToken } from '../session'

const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<>/{}+=·—'.split('')

interface Glyph {
  x: number
  y: number
  size: number
  speed: number
  alpha: number
  char: string
}

/** Faint dusty-purple characters drifting down; still when motion is reduced. */
function GlyphField() {
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
    let glyphs: Glyph[] = []
    let frame: number | null = null
    let width = 0
    let height = 0

    function seed() {
      const count = Math.max(28, Math.round((width * height) / 38000))
      glyphs = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        size: 11 + Math.random() * 15,
        speed: 0.08 + Math.random() * 0.35,
        alpha: 0.05 + Math.random() * 0.16,
        char: GLYPHS[Math.floor(Math.random() * GLYPHS.length)],
      }))
    }

    function draw() {
      if (!context) return
      context.clearRect(0, 0, width, height)
      context.textBaseline = 'middle'
      for (const glyph of glyphs) {
        context.font = `${glyph.size}px "Space Grotesk", ui-monospace, monospace`
        context.fillStyle = `rgba(139, 122, 168, ${glyph.alpha})`
        context.fillText(glyph.char, glyph.x, glyph.y)
      }
    }

    function step() {
      for (const glyph of glyphs) {
        glyph.y += glyph.speed
        if (glyph.y > height + 20) {
          glyph.y = -20
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

    function sync() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = window.innerWidth
      height = window.innerHeight
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    function restart() {
      stop()
      if (motionQuery.matches || document.hidden) {
        draw()
        return
      }
      frame = window.requestAnimationFrame(step)
    }

    function onResize() {
      sync()
      seed()
      restart()
    }

    sync()
    seed()
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
  }, [])

  return <canvas ref={canvasRef} className="signin-canvas" aria-hidden="true" />
}

function SignInView() {
  const navigate = useNavigate()
  const location = useLocation()
  const stateMessage =
    (location.state as { message?: string } | null)?.message ?? null

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (getToken()) return <Navigate to="/dashboard" replace />

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (busy) return

    setBusy(true)
    setError(null)
    try {
      const session = await login(username.trim(), password)
      setToken(session.token)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  const message = error ?? stateMessage

  return (
    <div className="signin">
      <GlyphField />
      <div className="signin-panel">
        <h1 className="signin-title">AXIOM</h1>
        <p className="signin-motto">
          Every claim traceable. Every conflict visible. Every uncertainty stated.
        </p>

        <form className="signin-form" onSubmit={onSubmit}>
          <label className="field">
            <span className="field-label">Username</span>
            <input
              className="input"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={busy}
              required
            />
          </label>
          <label className="field">
            <span className="field-label">Password</span>
            <input
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={busy}
              required
            />
          </label>

          <button
            className="button signin-submit"
            type="submit"
            disabled={busy || !username.trim() || !password}
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        {message ? (
          <p className="signin-error" role="alert">
            {message}
          </p>
        ) : null}

        <p className="signin-note">One local account. Not production authentication.</p>
      </div>
    </div>
  )
}

export default SignInView
