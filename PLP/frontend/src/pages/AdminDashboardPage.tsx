import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { AdminCandidateListItem } from "../types";

function formatDateInEST(dateString: string | null | undefined): string {
  if (!dateString) return "--";
  const date = new Date(dateString);
  return date.toLocaleString("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<AdminCandidateListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [evaluatorScores, setEvaluatorScores] = useState<Record<string, string>>({});
  const [submittingEvaluator, setSubmittingEvaluator] = useState<string | null>(null);

  async function loadList() {
    try {
      setLoading(true);
      const response = await api.adminList();
      setItems(response.items);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load admin dashboard.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadList();
  }, []);

  async function handleDelete(sessionId: string) {
    try {
      await api.deleteCandidate(sessionId);
      await loadList();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete candidate.");
    }
  }

  async function handleEvaluatorScoreSubmit(sessionId: string) {
    const scoreStr = evaluatorScores[sessionId];
    if (!scoreStr || scoreStr.trim() === "") {
      setError("Please enter a valid score.");
      return;
    }

    const score = parseFloat(scoreStr);
    if (isNaN(score) || score < 1 || score > 10) {
      setError("Score must be a number between 1 and 10.");
      return;
    }

    // Round to 2 decimal places
    const roundedScore = Math.round(score * 100) / 100;

    try {
      setSubmittingEvaluator(sessionId);
      setError(null);
      await api.setManualScore(sessionId, roundedScore, "Evaluator score");
      // Clear the input after successful submission
      setEvaluatorScores(prev => ({ ...prev, [sessionId]: "" }));
      await loadList();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to save evaluator score.");
    } finally {
      setSubmittingEvaluator(null);
    }
  }

  const filteredItems = items.filter((item) => {
    const haystack = `${item.candidate_id} ${item.name} ${item.email} ${item.status}`.toLowerCase();
    return haystack.includes(search.toLowerCase());
  });

  return (
    <section className="stack">
      {error ? <p className="muted">{error}</p> : null}
      <div className="table-panel">
        <h1 className="page-title">ADMIN DASHBOARD</h1>
        <div className="filter-row">
          <input
            className="field"
            placeholder="Filter by candidate, email, or status"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="spacer" />
        {loading ? (
          <div className="state-card">Loading admin sessions...</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th rowSpan={2}>Candidate ID</th>
                <th rowSpan={2}>Name</th>
                <th rowSpan={2}>Email</th>
                <th colSpan={2} className="scores-header">SCORES</th>
                <th rowSpan={2}>Submission</th>
                <th rowSpan={2}>Login</th>
                <th rowSpan={2}>Actions</th>
              </tr>
              <tr className="sub-header">
                <th>AI</th>
                <th>Evaluator</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr key={item.session_id}>
                  <td>{item.candidate_id}</td>
                  <td>{item.name}</td>
                  <td>{item.email}</td>
                  <td>{item.ai_score !== null && item.ai_score !== undefined 
                    ? item.ai_score.toFixed(2) 
                    : (item.submission_time ? "Evaluating" : "--")}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ minWidth: "3rem" }}>
                        {item.evaluator_score !== null && item.evaluator_score !== undefined 
                          ? item.evaluator_score.toFixed(2) 
                          : "--"}
                      </span>
                      <input
                        type="number"
                        min="1"
                        max="10"
                        step="0.01"
                        placeholder="1-10"
                        value={evaluatorScores[item.session_id] || ""}
                        onChange={(e) => setEvaluatorScores(prev => ({ ...prev, [item.session_id]: e.target.value }))}
                        style={{ width: "4rem", padding: "0.2rem" }}
                        disabled={submittingEvaluator === item.session_id}
                      />
                      <button
                        className="primary-button"
                        style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem" }}
                        onClick={() => handleEvaluatorScoreSubmit(item.session_id)}
                        disabled={submittingEvaluator === item.session_id}
                      >
                        {submittingEvaluator === item.session_id ? "..." : "Submit"}
                      </button>
                    </div>
                  </td>
                  <td>{formatDateInEST(item.submission_time)}</td>
                  <td>{formatDateInEST(item.login_time)}</td>
                  <td>
                    <button
                      className="secondary-button"
                      onClick={() => navigate(`/admin/candidates/${item.session_id}`)}
                    >
                      View response
                    </button>
                    <button className="delete-button" onClick={() => handleDelete(item.session_id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
