import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  errorMessage,
  listSources,
  searchChunks,
  type SearchHit,
  type SourceSummary,
} from '../api'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'

const DEBOUNCE_MS = 300
const SNIPPET_LENGTH = 300
const SNIPPET_LEAD = 90

interface Snippet {
  text: string
  /** Index of the matched term inside `text`, or -1. */
  at: number
  length: number
}

function firstTermIndex(haystack: string, query: string): { at: number; length: number } {
  const lower = haystack.toLowerCase()
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .map((term) => term.replace(/[^a-z0-9]/g, ''))
    .filter((term) => term.length > 2)

  let at = -1
  let length = 0
  for (const term of terms) {
    const index = lower.indexOf(term)
    if (index >= 0 && (at < 0 || index < at)) {
      at = index
      length = term.length
    }
  }
  return { at, length }
}

function buildSnippet(text: string, query: string): Snippet {
  const { at: absolute, length } = firstTermIndex(text, query)
  const anchor = absolute < 0 ? 0 : absolute
  const start = Math.max(0, anchor - SNIPPET_LEAD)
  const end = Math.min(text.length, start + SNIPPET_LENGTH)
  const slice = text.slice(start, end)
  const prefix = start > 0 ? '…' : ''
  const suffix = end < text.length ? '…' : ''
  const body = `${prefix}${slice}${suffix}`
  const at = absolute < 0 ? -1 : body.toLowerCase().indexOf(text.substr(absolute, length).toLowerCase())

  return { text: body, at, length }
}

function Highlighted({ snippet }: { snippet: Snippet }) {
  if (snippet.at < 0) return <>{snippet.text}</>

  return (
    <>
      {snippet.text.slice(0, snippet.at)}
      <mark>{snippet.text.slice(snippet.at, snippet.at + snippet.length)}</mark>
      {snippet.text.slice(snippet.at + snippet.length)}
    </>
  )
}

function SearchView() {
  // The top bar sends the term in the URL: /search?q=…
  const [params] = useSearchParams()
  const urlQuery = params.get('q')
  const [query, setQuery] = useState(urlQuery ?? '')
  const [hits, setHits] = useState<SearchHit[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sources, setSources] = useState<Record<number, SourceSummary>>({})
  const navigate = useNavigate()

  useEffect(() => {
    if (urlQuery !== null) setQuery(urlQuery)
  }, [urlQuery])

  useEffect(() => {
    let cancelled = false
    listSources()
      .then((list) => {
        if (cancelled) return
        const map: Record<number, SourceSummary> = {}
        for (const source of list) map[source.id] = source
        setSources(map)
      })
      .catch(() => {
        // Titles simply stay missing; the result still links to its source.
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const term = query.trim()
    if (!term) {
      setHits(null)
      setError(null)
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)

    const handle = window.setTimeout(() => {
      searchChunks(term)
        .then((results) => {
          if (cancelled) return
          setHits(results)
          setError(null)
        })
        .catch((err) => {
          if (cancelled) return
          setHits([])
          setError(errorMessage(err))
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, DEBOUNCE_MS)

    return () => {
      cancelled = true
      window.clearTimeout(handle)
    }
  }, [query])

  const term = query.trim()

  const results = useMemo(
    () =>
      (hits ?? []).map((hit) => ({
        hit,
        snippet: buildSnippet(hit.text, term),
        source: sources[hit.source_id],
      })),
    [hits, sources, term],
  )

  function openHit(hit: SearchHit) {
    navigate(`/sources?source=${hit.source_id}&chunk=${hit.chunk_id}`)
  }

  return (
    <div className="search">
      <PageHeader
        eyebrow="Search"
        title="Search"
        description="Full-text search over every stored chunk. Click a passage to open it in its source."
      />

      <section className="card">
        <label className="field-label" htmlFor="search-query">
          Search passages
        </label>
        <div className="search-box">
          <input
            id="search-query"
            className="input"
            type="search"
            value={query}
            placeholder="ionosphere"
            aria-label="Search passages"
            onChange={(event) => setQuery(event.target.value)}
          />
          <span className="muted small">{loading ? 'Searching…' : `${results.length} shown`}</span>
        </div>
      </section>

      {error ? (
        <div className="alert alert-error" role="alert">
          {error}
        </div>
      ) : null}

      {!term ? (
        <section className="card">
          <EmptyState
            title="Type a word or phrase to search."
            body="Results are ranked by PostgreSQL full-text search."
            action={{
              label: 'Focus the search box',
              onClick: () => document.getElementById('search-query')?.focus(),
            }}
          />
        </section>
      ) : null}

      {term && !loading && hits !== null && hits.length === 0 ? (
        <section className="card">
          <EmptyState
            title="No passages match that search."
            body="Try a different word or phrase."
            action={{ label: 'Clear the search', onClick: () => setQuery('') }}
          />
        </section>
      ) : null}

      {results.length > 0 ? (
        <ul className="result-list">
          {results.map(({ hit, snippet, source }) => (
            <li key={hit.chunk_id}>
              <button
                className="result"
                type="button"
                onClick={() => openHit(hit)}
                title="Open this passage in the source"
              >
                <span className="result-head">
                  <span className="result-source">{source?.title ?? `Source #${hit.source_id}`}</span>
                  <span className="muted small">chunk {hit.position}</span>
                </span>
                <span className="result-meta muted small">
                  {source?.doc_date ? `Doc date ${source.doc_date}` : 'No doc date'}
                  {' · '}
                  {source?.author ? `Author ${source.author}` : 'No author'}
                  {' · rank '}
                  {hit.rank.toFixed(3)}
                </span>
                <span className="result-snippet">
                  <Highlighted snippet={snippet} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

export default SearchView
