import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  errorMessage,
  listChunks,
  listSources,
  uploadSource,
  type Chunk,
  type SourceSummary,
} from '../api'

function formatDate(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

function SourcesView() {
  const [sources, setSources] = useState<SourceSummary[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [loadingList, setLoadingList] = useState(true)

  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [docDate, setDocDate] = useState('')
  const [author, setAuthor] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  // A ref, not the `uploading` state: two submits in the same tick both see the
  // old state value, so a fast double click could upload the file twice.
  const uploadInFlight = useRef(false)

  // Deep link from the Search view: /sources?source=<id>&chunk=<id>
  const [params] = useSearchParams()
  const targetSource = Number(params.get('source')) || null
  const targetChunk = Number(params.get('chunk')) || null

  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [chunksBySource, setChunksBySource] = useState<Record<number, Chunk[]>>({})
  const [chunkErrors, setChunkErrors] = useState<Record<number, string>>({})
  const [loadingChunksFor, setLoadingChunksFor] = useState<number | null>(null)

  async function loadSources() {
    setLoadingList(true)
    try {
      setSources(await listSources())
      setListError(null)
    } catch (err) {
      setListError(errorMessage(err))
    } finally {
      setLoadingList(false)
    }
  }

  useEffect(() => {
    void loadSources()
  }, [])

  // Open the source a search result points at, once the list has arrived.
  useEffect(() => {
    if (!targetSource || !sources) return
    if (expandedId === targetSource) return
    const source = sources.find((item) => item.id === targetSource)
    if (source) void toggleSource(source)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetSource, sources])

  // Then bring the exact chunk into view. The delay lets the opened source's
  // chunks finish laying out; scrolling in the same tick lands short.
  useEffect(() => {
    if (!targetChunk || !targetSource) return
    if (!chunksBySource[targetSource]) return

    const timer = window.setTimeout(() => {
      const element = document.getElementById(`chunk-${targetChunk}`)
      if (!element) return

      // Instant, not smooth: a backgrounded tab never runs the smooth-scroll
      // animation, and reduced-motion users should not get it either.
      element.classList.add('chunk-target')
      element.scrollIntoView({ block: 'start', behavior: 'auto' })
    }, 120)

    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetChunk, targetSource, chunksBySource])

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (uploadInFlight.current) return
    if (!file) {
      setUploadError('Choose a .txt, .md or .pdf file first.')
      return
    }

    uploadInFlight.current = true
    setUploading(true)
    setUploadError(null)
    setNotice(null)
    try {
      const created = await uploadSource(
        file,
        title.trim() || undefined,
        docDate || undefined,
        author.trim() || undefined,
      )
      setNotice(`Uploaded “${created.title}” (${created.chunk_count} chunks).`)
      setFile(null)
      setTitle('')
      setDocDate('')
      setAuthor('')
      if (fileInput.current) fileInput.current.value = ''
      await loadSources()
    } catch (err) {
      setUploadError(errorMessage(err))
    } finally {
      uploadInFlight.current = false
      setUploading(false)
    }
  }

  async function toggleSource(source: SourceSummary) {
    if (expandedId === source.id) {
      setExpandedId(null)
      return
    }

    setExpandedId(source.id)
    if (chunksBySource[source.id]) return

    setLoadingChunksFor(source.id)
    try {
      const chunks = await listChunks(source.id)
      setChunksBySource((current) => ({ ...current, [source.id]: chunks }))
      setChunkErrors((current) => {
        const next = { ...current }
        delete next[source.id]
        return next
      })
    } catch (err) {
      setChunkErrors((current) => ({ ...current, [source.id]: errorMessage(err) }))
    } finally {
      setLoadingChunksFor(null)
    }
  }

  return (
    <div className="sources">
      <section className="panel">
        <h2 className="panel-title">Upload a source</h2>
        <form className="upload-form" onSubmit={onSubmit}>
          <label className="field">
            <span className="field-label">File (.txt, .md, .pdf)</span>
            <input
              className="input"
              type="file"
              accept=".txt,.md,.pdf"
              ref={fileInput}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              disabled={uploading}
            />
          </label>

          <div className="field-row">
            <label className="field">
              <span className="field-label">Title (optional)</span>
              <input
                className="input"
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                disabled={uploading}
              />
            </label>
            <label className="field">
              <span className="field-label">Doc date (optional)</span>
              <input
                className="input"
                type="date"
                value={docDate}
                onChange={(event) => setDocDate(event.target.value)}
                disabled={uploading}
              />
            </label>
            <label className="field">
              <span className="field-label">Author (optional)</span>
              <input
                className="input"
                type="text"
                value={author}
                onChange={(event) => setAuthor(event.target.value)}
                disabled={uploading}
              />
            </label>
          </div>

          <div className="form-actions">
            <button className="button" type="submit" disabled={uploading}>
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
            {uploading ? <span className="muted small">Sending the file to the backend…</span> : null}
          </div>
        </form>

        {uploadError ? (
          <div className="alert alert-error" role="alert">
            {uploadError}
          </div>
        ) : null}
        {notice ? <div className="alert alert-ok">{notice}</div> : null}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2 className="panel-title">Source library</h2>
          <button className="button button-secondary" type="button" onClick={() => void loadSources()}>
            Refresh
          </button>
        </div>

        {loadingList && sources === null ? <p className="muted">Loading sources…</p> : null}
        {listError ? (
          <div className="alert alert-error" role="alert">
            {listError}
          </div>
        ) : null}

        {sources && sources.length === 0 && !listError ? (
          <p className="empty">No sources yet. Upload a document to get started.</p>
        ) : null}

        {sources && sources.length > 0 ? (
          <ul className="source-list">
            {sources.map((source) => {
              const open = expandedId === source.id
              const chunks = chunksBySource[source.id]
              return (
                <li className="source" key={source.id}>
                  <button
                    className="source-head"
                    type="button"
                    aria-expanded={open}
                    onClick={() => void toggleSource(source)}
                  >
                    <span className="claim-toggle" aria-hidden="true">
                      {open ? '▾' : '▸'}
                    </span>
                    <span className="source-main">
                      <span className="source-title">{source.title}</span>
                      <span className="muted small">{source.filename}</span>
                    </span>
                    <span className="source-meta">
                      <span>{source.chunk_count} chunks</span>
                      <span className="muted small">{formatDate(source.uploaded_at)}</span>
                    </span>
                  </button>

                  <p className="source-facts muted small">
                    {source.doc_date ? `Doc date ${source.doc_date}` : 'No doc date'}
                    {' · '}
                    {source.author ? `Author ${source.author}` : 'No author'}
                  </p>

                  {open ? (
                    <div className="chunks">
                      {loadingChunksFor === source.id ? (
                        <p className="muted">Loading chunks…</p>
                      ) : chunkErrors[source.id] ? (
                        <div className="alert alert-error" role="alert">
                          {chunkErrors[source.id]}
                        </div>
                      ) : chunks && chunks.length === 0 ? (
                        <p className="empty">This source has no chunks.</p>
                      ) : (
                        chunks?.map((chunk) => (
                          <div className="chunk" id={`chunk-${chunk.id}`} key={chunk.id}>
                            <span className="chunk-position">#{chunk.position}</span>
                            <p className="chunk-text">{chunk.text}</p>
                          </div>
                        ))
                      )}
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ul>
        ) : null}
      </section>
    </div>
  )
}

export default SourcesView
