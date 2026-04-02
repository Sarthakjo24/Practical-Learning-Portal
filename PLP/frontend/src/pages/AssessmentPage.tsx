import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { AudioQuestionCard } from "../components/AudioQuestionCard";
import type { CandidateSessionDetail } from "../types";

export function AssessmentPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const [session, setSession] = useState<CandidateSessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingRecordings, setPendingRecordings] = useState<Record<string, File>>({});

  async function loadSession() {
    try {
      const detail = await api.sessionDetail(sessionId);
      setSession(detail);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load session.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSession();
  }, [sessionId]);

  function handleRecordingReady(questionId: string, file: File) {
    setPendingRecordings((current) => ({
      ...current,
      [questionId]: file,
    }));
  }

  async function handleSubmit() {
    try {
      setSubmitting(true);
      setError(null);
      await api.submitSession(sessionId, pendingRecordings);
      setPendingRecordings({});
      navigate(`/submitted/${sessionId}`, { replace: true });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="state-card">Loading assessment...</div>;
  }

  const readyToSubmit = session?.answers.every(
    (answer) => Boolean(answer.audio_url || pendingRecordings[answer.question_id])
  );

  return (
    <section className="stack">
      <div className="panel">
        <h1 className="page-title">{session?.module_title}</h1>
        <div className="badge-row">
          <span className="pill">{session?.candidate_id}</span>
          <span className="pill">{session?.status}</span>
          <span className="pill">{session?.answers.length ?? 0} questions</span>
        </div>
        <div className="spacer" />
        <p className="muted">
          Listen carefully, record each spoken response, and submit once at the end. All recorded
          answers will upload together when you press the final submit button.
        </p>
        {error ? <p className="muted">{error}</p> : null}
      </div>

      {session?.answers
        .slice()
        .sort((left, right) => left.display_order - right.display_order)
        .map((answer) => (
          <AudioQuestionCard
            key={answer.answer_id}
            answer={answer}
            pendingFile={pendingRecordings[answer.question_id] ?? null}
            onRecordingReady={handleRecordingReady}
          />
        ))}

      <div className="panel">
        <button
          className="primary-button"
          type="button"
          disabled={!readyToSubmit || submitting}
          onClick={handleSubmit}
        >
          {submitting ? "Submitting..." : "Submit assessment"}
        </button>
      </div>
    </section>
  );
}
