import { useEffect, useState } from 'react'
import {
  Navigate,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { currentUser } from './api'
import { clearToken, getToken, UNAUTHORIZED_EVENT } from './session'
import DashboardView from './views/DashboardView'
import GuideView from './views/GuideView'
import QueryView from './views/QueryView'
import ReportView from './views/ReportView'
import SearchView from './views/SearchView'
import SignInView from './views/SignInView'
import SourcesView from './views/SourcesView'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', end: false },
  { to: '/', label: 'Ask', end: true },
  { to: '/sources', label: 'Sources', end: false },
  { to: '/search', label: 'Search', end: false },
  { to: '/guide', label: 'Guide', end: false },
]

function RequireAuth() {
  const location = useLocation()
  if (!getToken()) {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

function Shell() {
  const navigate = useNavigate()
  const [username, setUsername] = useState<string | null>(null)

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
    return () => {
      cancelled = true
    }
  }, [])

  function onSignOut() {
    clearToken()
    navigate('/sign-in', { replace: true })
  }

  return (
    <div className="app">
      <div className="page-rule" aria-hidden="true" />
      <div className="shell">
        <aside className="sidebar">
          <div className="sidebar-mark" aria-hidden="true">
            AX<span>I</span>OM
          </div>
          <nav className="nav" aria-label="Main">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-foot">
            <p className="sidebar-user" title="Signed in as">
              {username ?? 'Signed in'}
            </p>
            <button className="nav-link nav-signout" type="button" onClick={onSignOut}>
              Sign out
            </button>
          </div>
        </aside>

        <div className="content">
          <header className="app-header">
            <h1 className="app-title">
              AXIOM<span className="app-title-dot" aria-hidden="true" />
            </h1>
            <p className="app-tagline">
              Every claim traceable. Every conflict visible. Every uncertainty stated.
            </p>
          </header>

          <main className="app-main">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
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
          <Route path="/" element={<QueryView />} />
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
