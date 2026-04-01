import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useSession } from "../auth/SessionProvider";
import type { ModuleSummary, UserProfile } from "../types";

export function CandidateDashboardPage() {
  const { user, refreshSession } = useSession();
  const navigate = useNavigate();
  const [modules, setModules] = useState<ModuleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyModule, setBusyModule] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        await refreshSession();
        const nextModules = await api.modules();
        setModules(nextModules);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load dashboard.");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, [refreshSession]);

  async function startAssessment(moduleSlug: string) {
    try {
      setBusyModule(moduleSlug);
      const session = await api.startSession(moduleSlug);
      navigate(`/assessment/${session.session_id}`);
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Failed to start the assessment.");
    } finally {
      setBusyModule(null);
    }
  }

  if (loading) {
    return <div className="state-card">Loading dashboard...</div>;
  }

  return (
    <section className="dashboard-grid">
      <div className="panel">
        <h1 className="page-title">Candidate dashboard</h1>
        <div className="stats-row">
          <div className="metric-card">
            <strong>{user?.candidate_code ?? "--"}</strong>
            Candidate ID
          </div>
          <div className="metric-card">
            <strong>{modules.length}</strong>
            Active modules
          </div>
        </div>
        <div className="spacer" />
        <p className="muted">
          Welcome, {user?.full_name}. Start your assessment when you are ready. Scores remain
          hidden from the candidate interface after submission.
        </p>
        {error ? <p className="muted">{error}</p> : null}
      </div>

      <div className="panel">
        <h2 className="section-title">Available modules</h2>
        <div className="stack">
          {modules.map((module) => (
            <div className="module-card" key={module.id}>
              <h3>{module.title}</h3>
              <p className="muted">{module.description ?? "Customer handling assessment module."}</p>
              <div className="badge-row">
                <span className="pill">{module.question_count} questions</span>
                <span className="pill">{module.slug}</span>
              </div>
              <div className="spacer" />
              <button
                className="primary-button"
                type="button"
                disabled={busyModule === module.slug}
                onClick={() => startAssessment(module.slug)}
              >
                {busyModule === module.slug ? "Preparing..." : "Start assessment"}
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
