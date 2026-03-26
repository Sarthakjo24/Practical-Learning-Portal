import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <section className="hero-grid">
      <div className="panel hero-copy">
        <div className="badge-row">
          <span className="pill">Behavior-led assessments</span>
          <span className="pill">AI evaluation pipeline</span>
          <span className="pill">Auth0 secured</span>
        </div>
        <div className="spacer" />
        <h1>Practical learning for customer-facing judgment.</h1>
        <p>
          Measure empathy, respect, tone, and handling approach through real audio scenarios instead
          of checkbox quizzes.
        </p>
        <div className="hero-actions">
          <Link className="primary-button" to="/login">
            Enter the portal
          </Link>
          <a
            className="secondary-button"
            href="https://mngautomation.example.com"
            target="_blank"
            rel="noreferrer"
          >
            Visit MnGAutomation
          </a>
        </div>
      </div>

      <div className="panel">
        <h2 className="section-title">Assessment loop</h2>
        <div className="stack">
          <div className="metric-card">
            <strong>5</strong>
            Randomized scenarios per session
          </div>
          <div className="metric-card">
            <strong>AI</strong>
            Faster Whisper plus OpenAI evaluation
          </div>
          <div className="metric-card">
            <strong>Admin</strong>
            Manual score override and transcript review
          </div>
        </div>
      </div>
    </section>
  );
}
