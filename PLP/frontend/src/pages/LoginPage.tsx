import { useAuth0 } from "@auth0/auth0-react";

export function LoginPage() {
  const { loginWithRedirect, isLoading } = useAuth0();

  return (
    <section className="dashboard-grid">
      <div className="panel">
        <h1 className="page-title">Secure sign-in</h1>
        <p className="muted">
          Use your Google or Microsoft account through Auth0. Your candidate profile is created
          automatically after authentication.
        </p>
        <div className="hero-actions">
          <button className="primary-button" disabled={isLoading} onClick={() => loginWithRedirect()}>
            {isLoading ? "Loading..." : "Continue with Auth0"}
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
