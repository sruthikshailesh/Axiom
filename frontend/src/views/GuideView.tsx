import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'

function GuideView() {
  return (
    <div className="guide">
      <PageHeader
        eyebrow="Guide"
        title="Guide"
        description="How AXIOM turns documents into claims you can check, status by status."
      />

      <section className="card">
        <h2 className="card-title">What AXIOM does</h2>
        <p>
          AXIOM reads your team's documents and answers a question with separate claims
          instead of one summary. Every claim shows the sentence it came from, a label for
          how far it can be trusted, and the document behind it.
        </p>
      </section>

      <section className="card">
        <h2 className="card-title">Step by step</h2>
        <ol className="guide-list">
          <li>
            <strong>Upload documents.</strong> Open <Link to="/sources">Sources</Link> and
            add a file. Give it a date and an author if you have them — they decide which
            decision is newer.
          </li>
          <li>
            <strong>Ask a question.</strong> On <Link to="/ask">Ask</Link>, ask about one
            topic. AXIOM searches the chunks, extracts claims and checks every quote
            against the text it came from.
          </li>
          <li>
            <strong>Read the report.</strong> Each claim has a status, a quote and its
            source. Conflicts and supersessions are listed underneath, with the two claims
            and the reason they were paired.
          </li>
        </ol>
      </section>

      <section className="card">
        <h2 className="card-title">What documents it accepts</h2>
        <p>
          AXIOM accepts <code>.txt</code>, <code>.md</code> and text-based{' '}
          <code>.pdf</code> files up to 10 MB each; scanned PDFs are rejected because OCR
          is not built, so a PDF needs a text layer to be usable.
        </p>
      </section>

      <section className="card">
        <h2 className="card-title">Why the optional fields matter</h2>
        <p>
          The document date and author decide which decision is newer and who owns a claim:
          a claim inherits the date and author of the document it came from, and the
          verifier uses the dates to decide whether a newer document replaced an older one.
          Without a date, a supersession cannot be decided, and the pair stays a conflict
          or an uncertain claim.
        </p>
      </section>

      <section className="card">
        <h2 className="card-title">Good questions</h2>
        <p>
          Ask about one topic, such as “What search technology does this project use?”.
          Avoid questions that span unrelated topics: the pipeline extracts one claim per
          passage, so a question that mixes subjects produces claims that are hard to
          compare.
        </p>
      </section>

      <section className="card">
        <h2 className="card-title">What the statuses mean</h2>
        <dl className="status-list">
          <div>
            <dt>
              <span className="badge badge-verified">verified</span>
            </dt>
            <dd>
              More than one source supports the claim, so it is safe to act on. Example:
              the architecture note and the planning notes both say PostgreSQL full-text
              search is in use.
            </dd>
          </div>
          <div>
            <dt>
              <span className="badge badge-conflict">conflict</span>
            </dt>
            <dd>
              Two sources say things that cannot both be true. Example: one note says
              Elasticsearch still ranks documents, another says it was dropped.
            </dd>
          </div>
          <div>
            <dt>
              <span className="badge badge-uncertain">uncertain</span>
            </dt>
            <dd>
              Only one source supports the claim, so it is a single unconfirmed statement.
              Example: a lone status note saying an index will be added.
            </dd>
          </div>
          <div>
            <dt>
              <span className="badge badge-superseded">superseded</span>
            </dt>
            <dd>
              A newer document replaces this claim, so the claim is history. Example: an
              early design note naming Elasticsearch is superseded by a later architecture
              note naming PostgreSQL.
            </dd>
          </div>
        </dl>
      </section>

      <section className="card">
        <h2 className="card-title">Limitations</h2>
        <ul className="guide-list">
          <li>
            Results depend on the language model's output: claim wording, and therefore
            which conflicts and supersessions are found, varies between models and between
            runs.
          </li>
          <li>
            Sign-in is a single local account for one person on one machine. There is no
            user management and no protection beyond that, so it is not production
            authentication.
          </li>
          <li>
            The demo data is synthetic: four fictional documents about a project called
            Lantern, written to exercise the pipeline.
          </li>
        </ul>
      </section>
    </div>
  )
}

export default GuideView
