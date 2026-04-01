import { useEffect, useState } from "react";
import { api } from "../api";
import type { AdminCandidateDetail, AdminCandidateListItem } from "../types";

export function AdminDashboardPage() {
  const [items, setItems] = useState<AdminCandidateListItem[]>([]);
  const [selected, setSelected] = useState<AdminCandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [manualScore, setManualScore] = useState("");
  const [notes, setNotes] = useState("");
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

  async function handleSelect(sessionId: string) {
    try {
      const detail = await api.adminDetail(sessionId);
      setSelected(detail);
      setManualScore(detail.latest_manual_score?.manual_score?.toString() ?? "");
      setNotes(detail.latest_manual_score?.notes ?? "");
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : "Failed to load candidate detail.");
    }
  }

  async function handleSaveManualScore() {
    if (!selected || !manualScore) {
      return;
    }

    try {
      await api.setManualScore(selected.session_id, Number(manualScore), notes);
      await handleSelect(selected.session_id);
      await loadList();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save manual score.");
    }
  }

  async function handleDelete(sessionId: string) {
    try {
      await api.deleteCandidate(sessionId);
      if (selected?.session_id === sessionId) {
        setSelected(null);
      }
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
    <section className="admin-grid">
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
                  <td>{item.ai_score ?? "--"}</td>
                  <td>{item.evaluator_score ?? "--"}</td>
                  <td>{item.submission_time ?? "--"}</td>
                  <td>{item.login_time}</td>
                  <td>
                    <button className="secondary-button" onClick={() => handleSelect(item.session_id)}>
                      View
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

      <div className="detail-panel">
        <h2 className="section-title">Candidate detail</h2>
        {error ? <p className="muted">{error}</p> : null}
        {!selected ? (
          <p className="muted">Select a candidate session to review transcripts, AI insights, and manual scoring.</p>
        ) : (
          <div className="stack">
            <div className="module-card">
              <strong>{selected.name}</strong>
              <p className="muted">{selected.email}</p>
              <div className="badge-row">
                <span className="pill">{selected.candidate_id}</span>
                <span className="pill">{selected.status}</span>
                <span className="pill">AI: {selected.ai_score ?? "--"}</span>
              </div>
            </div>

            <div className="module-card">
              <h3>Manual score override</h3>
              <input
                className="field"
                placeholder="0-100"
                value={manualScore}
                onChange={(event) => setManualScore(event.target.value)}
              />
              <div className="spacer" />
              <textarea
                className="textarea"
                placeholder="Reviewer notes"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
              <div className="spacer" />
              <button className="primary-button" onClick={handleSaveManualScore}>
                Save manual score
              </button>
            </div>

            {selected.answers.map((answer) => (
              <div className="module-card" key={answer.answer_id}>
                <strong>
                  Q{answer.display_order}: {answer.question_title}
                </strong>
                <audio controls src={answer.question_audio_url} style={{ width: "100%", marginTop: "0.6rem" }} />
                {answer.audio_url ? (
                  <audio controls src={answer.audio_url} style={{ width: "100%", marginTop: "0.6rem" }} />
                ) : null}
                {answer.transcript_text ? <p className="muted">{answer.transcript_text}</p> : null}
                {answer.evaluation ? (
                  <div className="badge-row">
                    <span className="pill">Score {answer.evaluation.total_score}</span>
                    <span className="pill">Empathy {answer.evaluation.empathy_score}</span>
                    <span className="pill">Engagement {answer.evaluation.engagement_score}</span>
                  </div>
                ) : null}
                {answer.standard_responses.length > 0 ? (
                  <div className="module-card">
                    <strong>Standard responses</strong>
                    {answer.standard_responses.map((response, index) => (
                      <p className="muted" key={`${answer.answer_id}-${index}`}>
                        {index + 1}. {response}
                      </p>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
