import { useEffect, useRef, useState } from 'react'
import {
  Link,
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { currentUser, dashboardSummary, errorMessage, startDemoRun, type DashboardSummary } from './api'
import {
  AxiomMark,
  BookIcon,
  ChevronIcon,
  GridIcon,
  MenuIcon,
  PanelIcon,
  PlayIcon,
  SearchIcon,
  SparkIcon,
  UploadIcon,
} from './icons'
import { clearToken, getToken, UNAUTHORIZED_EVENT } from './session'
import { rememberRun } from './lastRun'
import DashboardView from './views/DashboardView'
import GuideView from './views/GuideView'
import QueryView from './views/QueryView'
import ReportView from './views/ReportView'
import SearchView from './views/SearchView'
import SignInView from './views/SignInView'
import SourcesView from './views/SourcesView'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Overview', icon: GridIcon, end: false },
  { to: '/ask', label: 'Ask', icon: SparkIcon, end: false },
  { to: '/sources', label: 'Sources', icon: UploadIcon, end: false },
  { to: '/search', label: 'Search', icon: SearchIcon, end: false },
  { to: '/guide', label: 'Guide', icon: BookIcon, end: false },
]

function pageTitle(pathname: string): string {
  if (pathname.startsWith('/runs/')) return 'Report'
  if (pathname.startsWith('/sources')) return 'Sources'
  if (pathname.startsWith('/search')) return 'Search'
  if (pathname.startsWith('/guide')) return 'Guide'
  if (pathname.startsWith('/ask') || pathname === '/') return 'Ask'
  return 'Overview'
}

function RequireAuth() {
  const location = useLocation()
  if (!getToken()) {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

function Shell() {
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState<string | null>(null)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [recentsOpen, setRecentsOpen] = useState(true)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [navOpen, setNavOpen] = useState(false)
  const [term, setTerm] = useState('')
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoError, setDemoError] = useState<string | null>(null)

  const searchRef = useRef<HTMLInputElement>(null)
  const userMenuRef = useRef<HTMLDivElement>(null)
  const topUserMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    currentUser()
      .then((user) => {
        if (!cancelled) setUsername(user.username)
      })
      .catch(() => {
        // A 401 is handled by the app-level listener; anything else leaves the
        // label showing the generic fallback.
      })
    dashboardSummary()
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch(() => {
        // The sidebar simply shows its empty states.
      })
    return () => {
      cancelled = true
    }
  }, [])

  // ⌘K / Ctrl+K focuses the top-bar search from anywhere in the shell.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchRef.current?.focus()
        searchRef.current?.select()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  // Close the user menu on a click outside it, or on Escape.
  useEffect(() => {
    if (!userMenuOpen) return

    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node
      const insideSidebar = userMenuRef.current?.contains(target)
      const insideTopbar = topUserMenuRef.current?.contains(target)
      if (!insideSidebar && !insideTopbar) setUserMenuOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setUserMenuOpen(false)
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [userMenuOpen])

  useEffect(() => {
    setNavOpen(false)
  }, [location.pathname])

  function onSignOut() {
    clearToken()
    navigate('/sign-in', { replace: true })
  }

  function onSearchSubmit(event: React.FormEvent) {
    event.preventDefault()
    const value = term.trim()
    navigate(value ? `/search?q=${encodeURIComponent(value)}` : '/search')
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
    } finally {
      setDemoLoading(false)
    }
  }

  const latestRunId = summary?.latest_run?.id ?? null
  const recents = summary?.recent_runs.slice(0, 5) ?? []
  const currentPath = location.pathname

  return (
    <div className="app">
      <button
        className="nav-backdrop"
        type="button"
        aria-label="Close navigation"
        tabIndex={navOpen ? 0 : -1}
        onClick={() => setNavOpen(false)}
        data-open={navOpen ? 'true' : 'false'}
      />

      <div className="shell">
        <aside
          className={`sidebar${collapsed ? ' sidebar-collapsed' : ''}${navOpen ? ' sidebar-open' : ''}`}
          aria-label="Sidebar"
        >
          <div className="side-brand">
            <span className="side-mark">
              <AxiomMark />
            </span>
            <span className="side-wordmark">
              <strong>AXIOM</strong>
            </span>
            <span className="side-brand-actions">
              <Link className="icon-button" to="/search" aria-label="Search passages" title="Search passages">
                <SearchIcon />
              </Link>
              <button
                className="icon-button collapse-button"
                type="button"
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                aria-expanded={!collapsed}
                title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                onClick={() => setCollapsed((value) => !value)}
              >
                <PanelIcon />
              </button>
              <button
                className="icon-button close-nav"
                type="button"
                aria-label="Close navigation"
                onClick={() => setNavOpen(false)}
              >
                <span aria-hidden="true">✕</span>
              </button>
            </span>
          </div>

          <p className="side-sub">Research intelligence</p>

          <button className="side-primary" type="button" onClick={() => navigate('/ask')}>
            <SparkIcon />
            <span className="side-label">New question</span>
          </button>

          <div className="side-card" aria-label="Quick actions">
            <Link className="quick-row" to="/sources" title="Upload documents">
              <UploadIcon />
              <span className="side-label">Upload documents</span>
            </Link>
            <Link className="quick-row" to="/ask" title="Ask a question">
              <SparkIcon />
              <span className="side-label">Ask a question</span>
            </Link>
            <button
              className="quick-row"
              type="button"
              onClick={() => void onLoadDemo()}
              disabled={demoLoading}
              title="Load the synthetic demo documents"
            >
              <PlayIcon />
              <span className="side-label">{demoLoading ? 'Loading demo…' : 'Load demo'}</span>
            </button>
            {demoError ? (
              <p className="quick-error" role="alert">
                {demoError}
              </p>
            ) : null}
          </div>

          <nav className="nav" aria-label="Main">
            <p className="side-group-label">Navigation</p>
            {NAV_ITEMS.slice(0, 4).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                title={item.label}
              >
                <span className="nav-icon">
                  <item.icon />
                </span>
                <span className="side-label">{item.label}</span>
              </NavLink>
            ))}
            {latestRunId ? (
              <NavLink
                to={`/runs/${latestRunId}`}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                title="Report"
              >
                <span className="nav-icon">
                  <ReportIconSlot />
                </span>
                <span className="side-label">Report</span>
              </NavLink>
            ) : (
              <span
                className="nav-link nav-link-disabled"
                aria-disabled="true"
                title="Run a question first"
              >
                <span className="nav-icon">
                  <ReportIconSlot />
                </span>
                <span className="side-label">Report</span>
              </span>
            )}
            <NavLink
              to="/guide"
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              title="Guide"
            >
              <span className="nav-icon">
                <BookIcon />
              </span>
              <span className="side-label">Guide</span>
            </NavLink>
          </nav>

          <div className="recents">
            <button
              className="recents-toggle"
              type="button"
              aria-expanded={recentsOpen}
              onClick={() => setRecentsOpen((value) => !value)}
            >
              <span>Recents</span>
              <ChevronIcon open={recentsOpen} />
            </button>
            {recentsOpen ? (
              recents.length ? (
                <ul className="recent-list">
                  {recents.map((run) => (
                    <li key={run.id}>
                      <Link className="recent-row" to={`/runs/${run.id}`} title={run.question}>
                        <span className="recent-question">{run.question}</span>
                        <span className={`recent-status recent-status-${run.status}`}>
                          {run.status}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="recents-empty">No runs yet.</p>
              )
            ) : null}
          </div>

          <div className="side-foot">
            <Link className="nav-link foot-guide" to="/guide" title="Guide">
              <span className="nav-icon">
                <BookIcon />
              </span>
              <span className="side-label">Guide</span>
            </Link>

            <div className="user-wrap" ref={userMenuRef}>
              {userMenuOpen ? (
                <div className="user-menu" role="menu">
                  <button className="menu-item" type="button" role="menuitem" onClick={onSignOut}>
                    Sign out
                  </button>
                </div>
              ) : null}
              <button
                className="user-button"
                type="button"
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
                onClick={() => setUserMenuOpen((value) => !value)}
              >
                <span className="user-avatar" aria-hidden="true">
                  {(username ?? 'A').slice(0, 1)}
                </span>
                <span className="user-meta">
                  <span className="user-name">{username ?? 'Signed in'}</span>
                  <span className="user-sub">Local account</span>
                </span>
                <ChevronIcon open={userMenuOpen} />
              </button>
            </div>
          </div>
        </aside>

        <div className="content">
          <header className="mobile-bar">
            <button
              className="icon-button"
              type="button"
              aria-label="Open navigation"
              aria-expanded={navOpen}
              onClick={() => setNavOpen(true)}
            >
              <MenuIcon />
            </button>
            <span className="mobile-mark">
              <AxiomMark size={22} />
            </span>
            <span className="mobile-wordmark">AXIOM</span>
            <Link className="icon-button" to="/search" aria-label="Search passages">
              <SearchIcon />
            </Link>
          </header>

          <header className="topbar">
            <span className="topbar-title">{pageTitle(currentPath)}</span>

            <form className="topbar-search" role="search" onSubmit={onSearchSubmit}>
              <SearchIcon />
              <input
                ref={searchRef}
                type="search"
                value={term}
                onChange={(event) => setTerm(event.target.value)}
                placeholder="Search passages…"
                aria-label="Search passages"
              />
              <kbd className="kbd-hint">⌘K</kbd>
            </form>

            <div className="topbar-user" ref={topUserMenuRef}>
              <button
                className="topbar-user-button"
                type="button"
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
                onClick={() => setUserMenuOpen((value) => !value)}
              >
                <span className="user-avatar" aria-hidden="true">
                  {(username ?? 'A').slice(0, 1)}
                </span>
                <span className="topbar-username">{username ?? 'Signed in'}</span>
                <ChevronIcon />
              </button>
              {userMenuOpen ? (
                <div className="user-menu topbar-menu" role="menu">
                  <button className="menu-item" type="button" role="menuitem" onClick={onSignOut}>
                    Sign out
                  </button>
                </div>
              ) : null}
            </div>
          </header>

          <main className="app-main">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}

/** The report icon, kept separate so the disabled and active rows match. */
function ReportIconSlot() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M13.5 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9Z" />
      <path d="M13.5 3.5V9H19" />
      <line x1="8.5" y1="13" x2="15.5" y2="13" />
      <line x1="8.5" y1="16.5" x2="13" y2="16.5" />
    </svg>
  )
}

function App() {
  const navigate = useNavigate()

  useEffect(() => {
    function onUnauthorized() {
      navigate('/sign-in', {
        replace: true,
        state: { message: 'Your session has ended. Sign in again.' },
      })
    }

    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [navigate])

  return (
    <Routes>
      <Route path="/sign-in" element={<SignInView />} />
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route path="/dashboard" element={<DashboardView />} />
          <Route path="/ask" element={<QueryView />} />
          <Route path="/" element={<Navigate to="/ask" replace />} />
          <Route path="/runs/:id" element={<ReportView />} />
          <Route path="/sources" element={<SourcesView />} />
          <Route path="/search" element={<SearchView />} />
          <Route path="/guide" element={<GuideView />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
