import { Link, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { useSession } from "./auth/SessionProvider";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { AdminResponsePage } from "./pages/AdminResponsePage";
import { AssessmentPage } from "./pages/AssessmentPage";
import { CandidateDashboardPage } from "./pages/CandidateDashboardPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { SubmissionSuccessPage } from "./pages/SubmissionSuccessPage";

function AppShell() {
  const { user, logout } = useSession();

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
          {user ? (
            <button className="ghost-button" onClick={() => void logout()}>
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
          <Route path="/submitted/:sessionId" element={<SubmissionSuccessPage />} />
          <Route
            path="/admin"
            element={
              <ProtectedRoute adminOnly>
                <AdminDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/candidates/:sessionId"
            element={
              <ProtectedRoute adminOnly>
                <AdminResponsePage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

export default AppShell;
