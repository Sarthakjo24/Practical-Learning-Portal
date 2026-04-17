import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { AdminCandidateDetail } from "../types";

export function AdminResponsePage() {
  const { sessionId = "" } = useParams();
  const [detail, setDetail] = useState<AdminCandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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

  function getEvaluationTimestamp(source: AdminCandidateDetail, answerId?: string): string | null {
    if (answerId) {
      const answer = source.answers.find((item) => item.answer_id === answerId);
      const evaluation = answer?.evaluation;
      if (!evaluation) {
        return null;
      }
      return JSON.stringify({
        total_score: evaluation.total_score,
        final_summary: evaluation.final_summary,
        strengths: evaluation.strengths,
        improvement_areas: evaluation.improvement_areas,
        created_at: evaluation.created_at ?? null,
      });
    }

    return JSON.stringify({
      completed_at: source.completed_at ?? null,
      ai_score: source.ai_score ?? null,
      answers: source.answers.map((answer) => ({
        answer_id: answer.answer_id,
        total_score: answer.evaluation?.total_score ?? null,
        final_summary: answer.evaluation?.final_summary ?? null,
        strengths: answer.evaluation?.strengths ?? [],
        improvement_areas: answer.evaluation?.improvement_areas ?? [],
        created_at: answer.evaluation?.created_at ?? null,
      })),
    });
  }

  async function waitForEvaluationUpdate(previousMarker: string | null, answerId?: string): Promise<boolean> {
    for (let attempt = 0; attempt < 10; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 3000));
      try {
        const latest = await api.adminDetail(sessionId);
        setDetail(latest);
        const nextMarker = getEvaluationTimestamp(latest, answerId);
        if (nextMarker && nextMarker !== previousMarker) {
          return true;
        }
      } catch {
        // Keep retrying within the polling window.
      }
    }

    return false;
  }

  async function handleReprocess() {
    if (!detail) {
      return;
    }

    try {
      setReprocessing(true);
      setError(null);
      const previousMarker = getEvaluationTimestamp(detail);
      const response = await api.reprocessSession(sessionId);
      setSuccessMessage(response.message || "Reprocessing requested. We're refreshing results...");
      const updated = await waitForEvaluationUpdate(previousMarker);
      setSuccessMessage(
        updated
          ? "Reprocessing completed and results were refreshed."
          : "Reprocessing is still running. Please refresh again shortly."
      );
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
      const previousMarker = getEvaluationTimestamp(detail, answerId);
      const response = await api.reevaluateAnswer(answerId);
      setSuccessMessage(response.message || "Reevaluation requested. We're refreshing this response...");
      const updated = await waitForEvaluationUpdate(previousMarker, answerId);
      setSuccessMessage(
        updated
          ? "Reevaluation completed and the response panel was refreshed."
          : "Reevaluation is still running. Please refresh again shortly."
      );
    } catch (reevaluateError) {
      setError(reevaluateError instanceof Error ? reevaluateError.message : "Failed to start reevaluation.");
    } finally {
      setReevaluatingAnswerId(null);
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
            <strong>{detail.session_id}</strong>
            Session ID
          </div>
          <div className="metric-card">
            <strong>{detail.ai_score ?? "--"}</strong>
            Total AI score
          </div>
        </div>
        {detail.overall_performance_summary ? (
          <div className="module-card">
            <strong>Overall performance summary</strong>
            <p className="muted">{detail.overall_performance_summary}</p>
          </div>
        ) : null}
      </div>

      {detail.answers
        .slice()
        .sort((left, right) => left.display_order - right.display_order)
        .map((answer) => (
          <div className="module-card" key={answer.answer_id}>
            <h2 className="section-title">
              Question {answer.display_order}: {answer.question_title || answer.question_code}
            </h2>
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
                <p className="muted">{answer.evaluation.final_summary || "Evaluation complete."}</p>
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
