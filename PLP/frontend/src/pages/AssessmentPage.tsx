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
  const [uploadingQuestionId, setUploadingQuestionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  async function handleUpload(questionId: string, file: File) {
    try {
      setUploadingQuestionId(questionId);
      await api.uploadAnswer(sessionId, questionId, file);
      await loadSession();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed.");
    } finally {
      setUploadingQuestionId(null);
    }
  }

  async function handleSubmit() {
    try {
      setSubmitting(true);
      await api.submitSession(sessionId);
      navigate(`/submitted/${sessionId}`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="state-card">Loading assessment...</div>;
  }

  const readyToSubmit = session?.answers.every((answer) => Boolean(answer.audio_url));

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
          Listen carefully, record each spoken response, upload it, and submit only after all five
          answers are ready.
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
            uploading={uploadingQuestionId === answer.question_id}
            onUpload={handleUpload}
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
