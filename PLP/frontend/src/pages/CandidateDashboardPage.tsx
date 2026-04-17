import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useSession } from "../auth/SessionProvider";
import type { ModuleSummary } from "../types";

export function CandidateDashboardPage() {
  const { user, logout } = useSession();
  const navigate = useNavigate();
  const [modules, setModules] = useState<ModuleSummary[]>([]);
  const [selectedModuleSlug, setSelectedModuleSlug] = useState<string | null>(null);
  const [modulesExpanded, setModulesExpanded] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busyModule, setBusyModule] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showProfile, setShowProfile] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        setError(null);
        const nextModules = await api.modules();
        setModules(nextModules);

        const preferredModule =
          nextModules.find(
            (module) =>
              module.title.trim().toLowerCase() === "customer centricity" ||
              module.slug.toLowerCase().includes("customer")
          ) ?? nextModules[0] ?? null;

        setSelectedModuleSlug((current) => {
          if (current && nextModules.some((module) => module.slug === current)) {
            return current;
          }
          return preferredModule?.slug ?? null;
        });
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load dashboard.");
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, []);

  function greetingMessage(): string {
    const hour = new Date().getHours();
    if (hour < 12) {
      return "Good morning";
    }
    if (hour < 17) {
      return "Good afternoon";
    }
    return "Good evening";
  }

  async function startAssessment(moduleSlug: string) {
    try {
      setBusyModule(moduleSlug);
      setSelectedModuleSlug(moduleSlug);
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

  const customerCentricityModule =
    modules.find(
      (module) =>
        module.title.trim().toLowerCase() === "customer centricity" ||
        module.slug.toLowerCase().includes("customer")
    ) ?? modules[0] ?? null;
  const selectedModule =
    modules.find((module) => module.slug === selectedModuleSlug) ?? customerCentricityModule;

  return (
    <section className="candidate-portal-shell">
      <aside className="panel candidate-sidebar">
        <div>
          <button
            className={`candidate-sidebar-item ${!showProfile ? "active" : ""}`}
            type="button"
            onClick={() => setShowProfile(false)}
          >
            Dashboard
          </button>

          <div className="spacer" />

          <button
            className={`candidate-sidebar-item candidate-sidebar-dropdown ${modulesExpanded ? "active" : ""}`}
            type="button"
            onClick={() => setModulesExpanded((current) => !current)}
          >
            <span>Modules</span>
            <span>{modulesExpanded ? "▾" : "▸"}</span>
          </button>

          {modulesExpanded ? (
            <div className="candidate-sidebar-submenu">
              {customerCentricityModule ? (
                <button
                  className={`candidate-sidebar-item candidate-sidebar-subitem ${
                    selectedModuleSlug === customerCentricityModule.slug ? "active" : ""
                  }`}
                  type="button"
                  disabled={busyModule !== null}
                  onClick={() => {
                    setSelectedModuleSlug(customerCentricityModule.slug);
                    setShowProfile(false);
                    void startAssessment(customerCentricityModule.slug);
                  }}
                >
                  Customer Centricity
                </button>
              ) : (
                <p className="muted">No active modules available.</p>
              )}
            </div>
          ) : null}
        </div>

        <div className="candidate-sidebar-footer">
          <button
            className={`candidate-sidebar-item ${showProfile ? "active" : ""}`}
            type="button"
            onClick={() => setShowProfile((current) => !current)}
          >
            My Profile
          </button>
          <button className="candidate-sidebar-item" type="button" onClick={() => void logout()}>
            Log out
          </button>
        </div>
      </aside>

      <div className="candidate-main">
        <div className="panel">
          <h1 className="page-title">
            Hi, {user?.full_name ?? "Candidate"} {greetingMessage()}, Please select the module for
            your assessment in the sidebar!
          </h1>
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
          {error ? <p className="muted">{error}</p> : null}
        </div>

        {showProfile ? (
          <div className="panel">
            <h2 className="section-title">My Profile</h2>
            <p className="muted">Name: {user?.full_name ?? "--"}</p>
            <p className="muted">Candidate ID: {user?.candidate_code ?? "--"}</p>
            <p className="muted">Email: {user?.email ?? "--"}</p>
          </div>
        ) : null}

        <div className="panel">
          <h2 className="section-title">{selectedModule?.title ?? "Customer Centricity"}</h2>
          <p className="muted">
            Click the module in the sidebar to open the assessment.
          </p>
          {selectedModule ? (
            <div className="badge-row">
              <span className="pill">{selectedModule.question_count} questions</span>
              <span className="pill">{selectedModule.slug}</span>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
