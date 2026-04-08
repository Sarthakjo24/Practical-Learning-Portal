import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { AdminCandidateDetail } from "../types";

export function AdminResponsePage() {
  const { sessionId = "" } = useParams();
  const [detail, setDetail] = useState<AdminCandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [manualScore, setManualScore] = useState<number>(0);
  const [manualNotes, setManualNotes] = useState<string>("");
  const [savingManualScore, setSavingManualScore] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [reprocessing, setReprocessing] = useState(false);
  const [reevaluatingAnswerId, setReevaluatingAnswerId] = useState<string | null>(null);

  async function loadDetail(showLoader = true) {
    try {
      if (showLoader) {
        setLoading(true);
      }
      setError(null);
      const response = await api.adminDetail(sessionId);
      setDetail(response);
      setManualScore(response.latest_manual_score?.manual_score ?? 0);
      setManualNotes(response.latest_manual_score?.notes ?? "");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load candidate response.");
    } finally {
      if (showLoader) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  async function handleReprocess() {
    if (!detail) {
      return;
    }

    try {
      setReprocessing(true);
      setError(null);
      setSuccessMessage(null);
      const response = await api.reprocessSession(sessionId);
      setSuccessMessage(response.message || "Reprocessing started. Refresh in a few minutes to see updates.");
      await loadDetail(false);
    } catch (reprocessError) {
      setError(reprocessError instanceof Error ? reprocessError.message : "Failed to start reprocessing.");
    } finally {
      setReprocessing(false);
    }
  }

  async function handleReevaluateAnswer(answerId: string) {
    if (!detail) {
      return;
    }

    try {
      setReevaluatingAnswerId(answerId);
      setError(null);
      setSuccessMessage(null);
      const response = await api.reevaluateAnswer(answerId);
      setSuccessMessage(response.message || "Reevaluation started for this response.");
      await loadDetail(false);
    } catch (reevaluateError) {
      setError(reevaluateError instanceof Error ? reevaluateError.message : "Failed to start reevaluation.");
    } finally {
      setReevaluatingAnswerId(null);
    }
  }

  async function handleSaveManualScore() {
    if (!detail) {
      return;
    }

    try {
      setSavingManualScore(true);
      setError(null);
      setSuccessMessage(null);
      await api.setManualScore(sessionId, manualScore, manualNotes);
      setSuccessMessage("Manual score saved successfully.");
      await loadDetail(false);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to save manual score.");
    } finally {
      setSavingManualScore(false);
    }
  }

  if (loading) {
    return <div className="state-card">Loading candidate response...</div>;
  }

  if (!detail) {
    return (
      <section className="stack">
        <div className="panel">
          <h1 className="page-title">Candidate response</h1>
          <p className="muted">{error ?? "Candidate response not found."}</p>
          <div className="spacer" />
          <Link to="/admin" className="secondary-button">
            Back to admin
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="stack">
      <div className="panel">
        <Link to="/admin" className="secondary-button">
          Back to admin
        </Link>
        <div className="spacer" />
        <h1 className="page-title">Candidate response</h1>
        {error ? <p className="muted">{error}</p> : null}
        {successMessage ? <p className="success">{successMessage}</p> : null}
        <div className="stats-row">
          <div className="metric-card">
            <strong>{detail.name}</strong>
            Candidate name
          </div>
          <div className="metric-card">
            <strong>{detail.email}</strong>
            Email
          </div>
          <div className="metric-card">
            <strong>{detail.candidate_id}</strong>
            Candidate ID
          </div>
          <div className="metric-card">
            <strong>{detail.ai_score ?? "--"}</strong>
            Total AI score
          </div>
        </div>
      </div>

      {detail.answers
        .slice()
        .sort((left, right) => left.display_order - right.display_order)
        .map((answer) => (
          <div className="module-card" key={answer.answer_id}>
            <h2 className="section-title">Question: {answer.question_title || answer.question_code}</h2>
            <div className="badge-row">
              <span className="pill">Question ID: {answer.question_id}</span>
              <span className="pill">Question code: {answer.question_code}</span>
              <span className="pill">Score: {answer.evaluation?.total_score ?? "--"}</span>
              <button
                className="secondary-button"
                type="button"
                onClick={() => void handleReevaluateAnswer(answer.answer_id)}
                disabled={reprocessing || reevaluatingAnswerId === answer.answer_id}
              >
                {reevaluatingAnswerId === answer.answer_id ? "Reevaluating..." : "Reevaluate Response"}
              </button>
            </div>

            <div className="spacer" />

            <div>
              <p className="muted">Candidate response recording</p>
              {answer.audio_url ? (
                <audio
                  controls
                  controlsList="nodownload"
                  onContextMenu={(event) => event.preventDefault()}
                  src={answer.audio_url}
                  style={{ width: "100%", marginTop: "0.6rem" }}
                />
              ) : (
                <p className="muted">Candidate response not uploaded.</p>
              )}
            </div>

            <div className="spacer" />

            <div className="module-card">
              <strong>Transcript</strong>
              <p className="muted">{answer.transcript_text ?? "Transcription pending."}</p>
            </div>

            <div className="module-card">
              <strong>Standard responses</strong>
              {answer.standard_responses.length > 0 ? (
                <ul>
                  {answer.standard_responses.map((response, index) => (
                    <li key={index}>{response}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted">No standard responses configured for this question.</p>
              )}
            </div>

            {answer.evaluation ? (
              <div className="module-card">
                <h3 className="section-title">AI evaluation</h3>
                <div className="badge-row">
                  <span className="pill">Courtesy: {answer.evaluation.courtesy_score}</span>
                  <span className="pill">Respect: {answer.evaluation.respect_score}</span>
                  <span className="pill">Empathy: {answer.evaluation.empathy_score}</span>
                  <span className="pill">Tone: {answer.evaluation.tone_score}</span>
                </div>
                <div className="badge-row">
                  <span className="pill">Communication: {answer.evaluation.communication_clarity_score}</span>
                  <span className="pill">Engagement: {answer.evaluation.engagement_score}</span>
                  <span className="pill">Handling: {answer.evaluation.problem_handling_approach_score}</span>
                </div>
                <div className="spacer" />
                <div>
                  <strong>Summary</strong>
                  <p className="muted">{answer.evaluation.final_summary}</p>
                </div>
                {answer.evaluation.strengths.length > 0 ? (
                  <div>
                    <strong>Strengths</strong>
                    <ul>
                      {answer.evaluation.strengths.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {answer.evaluation.improvement_areas.length > 0 ? (
                  <div>
                    <strong>Improvement areas</strong>
                    <ul>
                      {answer.evaluation.improvement_areas.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="module-card">
                <p className="muted">AI evaluation is pending for this response.</p>
              </div>
            )}
          </div>
        ))}

      <div className="panel">
        <h2 className="section-title">Manual Scoring</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void handleSaveManualScore();
          }}
        >
          <div className="form-group">
            <label htmlFor="manual-score">Manual Score (0-100)</label>
            <input
              id="manual-score"
              type="number"
              min="0"
              max="100"
              value={manualScore}
              onChange={(event) => setManualScore(Number(event.target.value))}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="manual-notes">Notes</label>
            <textarea
              id="manual-notes"
              value={manualNotes}
              onChange={(event) => setManualNotes(event.target.value)}
              rows={4}
            />
          </div>
          <button type="submit" disabled={savingManualScore}>
            {savingManualScore ? "Saving..." : "Save Manual Score"}
          </button>
        </form>
      </div>

      <div className="panel">
        <h2 className="section-title">Reprocess Session</h2>
        <p className="muted">
          If transcription or evaluation failed, you can reprocess this session to retry the background tasks.
        </p>
        <button onClick={() => void handleReprocess()} disabled={reprocessing}>
          {reprocessing ? "Reprocessing..." : "Reprocess Session"}
        </button>
      </div>
    </section>
  );
}
