import { useParams } from 'react-router-dom'
import { getHomamBySlug } from '../data/homams.js'

function backToHomamsHref() {
  if (window.location.protocol === 'file:') {
    return '../index.html#homams'
  }
  return `${window.location.origin}/index.html#homams`
}

export default function HomamDetail() {
  const { slug } = useParams()
  const homam = getHomamBySlug(slug)

  if (!homam) {
    return (
      <div className="homam-page">
        <header className="homam-topbar">
          <a className="homam-back" href={backToHomamsHref()}>
            ← Back to Homams
          </a>
        </header>
        <div className="homam-container homam-not-found">
          <h1>Homam not found</h1>
          <p>This homam page does not exist or the link may be outdated.</p>
          <a className="homam-btn-secondary" href={backToHomamsHref()}>
            Return to Sacred Homams
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="homam-page">
      <header className="homam-topbar">
        <a className="homam-back" href={backToHomamsHref()}>
          ← Back to Homams
        </a>
      </header>

      <div className="homam-hero-block">
        <figure className="homam-hero-figure">
          <img
            className="homam-hero-img"
            src={homam.heroImage}
            alt={homam.heroAlt}
            width={480}
            height={480}
            loading="eager"
          />
          <figcaption className="homam-hero-figcaption">Devatha</figcaption>
        </figure>
        <div className="homam-hero-text">
          <p className="homam-deity-line">{homam.deityLabel}</p>
          <h1 className="homam-title">{homam.title}</h1>
        </div>
      </div>

      <main className="homam-container">
        <section className="homam-section" aria-labelledby="devatha-heading">
          <h2 id="devatha-heading" className="homam-section-title">
            About the Devatha
          </h2>
          {homam.devatha.map((p, i) => (
            <p key={i} className="homam-prose">
              {p}
            </p>
          ))}
        </section>

        <section className="homam-section" aria-labelledby="homam-heading">
          <h2 id="homam-heading" className="homam-section-title">
            About the Homam
          </h2>
          {homam.homam.map((p, i) => (
            <p key={i} className="homam-prose">
              {p}
            </p>
          ))}
        </section>

        <section className="homam-section" aria-labelledby="benefits-heading">
          <h2 id="benefits-heading" className="homam-section-title">
            Benefits of the Homam
          </h2>
          <ul className="homam-benefits-list">
            {homam.benefits.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </section>

        <p className="homam-footnote">
          Traditions vary by lineage; your ācārya may adapt procedures, timings, and dravyas.
        </p>
      </main>
    </div>
  )
}
