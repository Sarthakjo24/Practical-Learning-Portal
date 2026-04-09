import { useLocation } from "react-router-dom";
import { useSession } from "../auth/SessionProvider";

export function LoginPage() {
  const { login, loading } = useSession();
  const location = useLocation();
  const returnTo =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || "/dashboard";

  return (
    <section className="dashboard-grid">
      <div className="panel">
        <h1 className="page-title">Secure sign-in</h1>
        <p className="muted">
          Use Google or Microsoft through Auth0.
        </p>
        <div className="hero-actions">
          <button className="primary-button" disabled={loading} onClick={() => login("google", returnTo)}>
            Continue with Google
          </button>
          <button className="secondary-button" disabled={loading} onClick={() => login("microsoft", returnTo)}>
            Continue with Microsoft
          </button>
        </div>
      </div>

      <div className="panel">
        <h2 className="section-title">What happens next</h2>
        <div className="stack">
          <div className="module-card">Your name and email are synced into the candidate profile.</div>
          <div className="module-card">A unique candidate ID is generated server-side.</div>
          <div className="module-card">You can start the assessment and submit recordings from the portal.</div>
        </div>
      </div>
    </section>
  );
}
