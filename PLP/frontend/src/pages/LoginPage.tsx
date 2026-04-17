import { useLocation } from "react-router-dom";
import { useSession } from "../auth/SessionProvider";

export function LoginPage() {
  const { login, loading } = useSession();
  const location = useLocation();
  const returnTo =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || "/dashboard";

  return (
    <main className="hero-grid-centered">
      <div className="panel" style={{ maxWidth: "500px", textAlign: "center" }}>
        <div style={{ marginBottom: "1rem" }}>
          <p className="pill" style={{ display: "inline-block", marginBottom: "0.5rem" }}>
            AUTHENTICATION
          </p>
          <h1 style={{ fontSize: "2rem", margin: "0 0 0.5rem" }}>PLP SYSTEM LOGIN</h1>
        </div>
        <div className="stack" style={{ gap: "1rem" }}>
          <button
            className="auth-sso-button auth-button-google"
            disabled={loading}
            onClick={() => login("google", returnTo)}
          >
            <span className="auth-sso-icon">G+</span>
            Sign in with Google
          </button>
          <button
            className="auth-sso-button auth-button-microsoft"
            disabled={loading}
            onClick={() => login("microsoft", returnTo)}
          >
            <span className="auth-sso-icon">🔒</span>
            Sign in with Microsoft
          </button>
        </div>
      </div>
    </main>
  );
}
