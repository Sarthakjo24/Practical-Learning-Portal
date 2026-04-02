import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { AdminCandidateListItem } from "../types";

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<AdminCandidateListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

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

  const filteredItems = items.filter((item) => {
    const haystack = `${item.candidate_id} ${item.name} ${item.email} ${item.status}`.toLowerCase();
    return haystack.includes(search.toLowerCase());
  });

  return (
    <section className="stack">
      {error ? <p className="muted">{error}</p> : null}
      <div className="table-panel">
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
                <th>Candidate ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>AI</th>
                <th>Evaluator</th>
                <th>Submission</th>
                <th>Login</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr key={item.session_id}>
                  <td>{item.candidate_id}</td>
                  <td>{item.name}</td>
                  <td>{item.email}</td>
                  <td>{item.ai_score ?? (item.submission_time ? "Evaluating" : "--")}</td>
                  <td>{item.evaluator_score ?? "--"}</td>
                  <td>{item.submission_time ?? "--"}</td>
                  <td>{item.login_time}</td>
                  <td>
                    <button
                      className="secondary-button"
                      onClick={() => navigate(`/admin/candidates/${item.session_id}`)}
                    >
                      View response
                    </button>
                    <button className="ghost-button" onClick={() => handleDelete(item.session_id)}>
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
