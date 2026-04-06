import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { AdminCandidateDetail } from "../types";

export function AdminResponsePage() {
  const { sessionId = "" } = useParams();
  const [detail, setDetail] = useState<AdminCandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDetail() {
      try {
        setLoading(true);
        setError(null);
        const response = await api.adminDetail(sessionId);
        setDetail(response);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load candidate response.");
      } finally {
        setLoading(false);
      }
    }

    void loadDetail();
  }, [sessionId]);

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
    </section>
  );
}
