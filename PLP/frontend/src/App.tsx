import { Link, Route, Routes } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { AssessmentPage } from "./pages/AssessmentPage";
import { CandidateDashboardPage } from "./pages/CandidateDashboardPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { SubmissionSuccessPage } from "./pages/SubmissionSuccessPage";

function AppShell() {
  const { isAuthenticated, logout } = useAuth0();

  return (
    <div className="app-frame">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">PLP</span>
          <span>Practical Learning Portal</span>
        </Link>
        <nav className="topnav">
          <Link to="/dashboard">Candidate</Link>
          <Link to="/admin">Admin</Link>
          {isAuthenticated ? (
            <button
              className="ghost-button"
              onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
            >
              Sign out
            </button>
          ) : (
            <Link to="/login" className="ghost-button">
              Sign in
            </Link>
          )}
        </nav>
      </header>

      <main className="page-shell">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <CandidateDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/assessment/:sessionId"
            element={
              <ProtectedRoute>
                <AssessmentPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/submitted/:sessionId"
            element={
              <ProtectedRoute>
                <SubmissionSuccessPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute>
                <AdminDashboardPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

export default AppShell;
