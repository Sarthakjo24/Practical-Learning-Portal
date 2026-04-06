import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <section className="hero-grid-centered">
      <div className="panel hero-copy hero-centered">
        <div className="spacer" />
        <h1>Automation Assessment and Interview Portal</h1>
        <div className="spacer" />
        <div className="hero-actions">
          <Link className="primary-button" to="/login">
            PRACTICAL LEARNING PORTAL
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
    </section>
  );
}
