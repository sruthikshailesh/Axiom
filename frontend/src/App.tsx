import { NavLink, Route, Routes } from 'react-router-dom'
import { lastRunId } from './lastRun'
import QueryView from './views/QueryView'
import ReportView from './views/ReportView'
import SourcesView from './views/SourcesView'

function App() {
  const runId = lastRunId()

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">AXIOM</h1>
        <p className="app-tagline">
          Every claim traceable. Every conflict visible. Every uncertainty stated.
        </p>
      </header>

      <div className="layout">
        <nav className="app-nav" aria-label="Main">
          <NavLink to="/" end className="nav-link">
            Query
          </NavLink>
          {runId ? (
            <NavLink to={`/runs/${runId}`} className="nav-link">
              Report
            </NavLink>
          ) : (
            <span className="nav-link nav-link-disabled" title="Ask a question first">
              Report
            </span>
          )}
          <NavLink to="/sources" className="nav-link">
            Sources
          </NavLink>
        </nav>

        <main className="app-main">
          <Routes>
            <Route path="/" element={<QueryView />} />
            <Route path="/runs/:id" element={<ReportView />} />
            <Route path="/sources" element={<SourcesView />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default App
