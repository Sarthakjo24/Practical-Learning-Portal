import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { AudioQuestionCard } from "../components/AudioQuestionCard";
import { useSession } from "../auth/SessionProvider";
import type { CandidateSessionDetail } from "../types";

export function AssessmentPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const { logout } = useSession();
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

  function isAlreadySubmittedError(error: unknown): boolean {
    const errorText = error instanceof Error ? error.message.toLowerCase() : "";
    return errorText.includes("already submitted");
  }

  async function handleSubmit() {
    if (!window.confirm("Submit all responses? Once submitted, you will be logged out and redirected to the confirmation page.")) {
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      try {
        await api.submitSession(sessionId, pendingRecordings);
      } catch (bulkSubmitError) {
        if (isAlreadySubmittedError(bulkSubmitError)) {
          setPendingRecordings({});
          await logout(`/submitted/${sessionId}`);
          return;
        }

        const pendingEntries = Object.entries(pendingRecordings);
        if (pendingEntries.length === 0 || !session) {
          throw bulkSubmitError;
        }

        for (const answer of session.answers) {
          const pendingFile = pendingRecordings[answer.question_id];
          if (!pendingFile) {
            continue;
          }

          try {
            await api.uploadAnswer(sessionId, answer.question_id, pendingFile);
          } catch (uploadError) {
            if (isAlreadySubmittedError(uploadError)) {
              setPendingRecordings({});
              await logout(`/submitted/${sessionId}`);
              return;
            }
            throw uploadError;
          }
        }

        await api.submitSession(sessionId);
      }
      setPendingRecordings({});
      await logout(`/submitted/${sessionId}`);
    } catch (submitError) {
      if (isAlreadySubmittedError(submitError)) {
        setPendingRecordings({});
        await logout(`/submitted/${sessionId}`);
        return;
      }
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
  const scenarioCount = session?.answers.length ?? 0;

  return (
    <section className="stack">
      <div className="panel">
        <h1 className="page-title">{session?.module_title}</h1>
        <div className="badge-row">
          <span className="pill">{session?.candidate_id}</span>
          <span className="pill">{session?.answers.length ?? 0} questions</span>
        </div>
        <div className="spacer" />
        <div className="module-card">
          <p className="muted">
            <strong>INSTRUCTIONS :</strong> There are total of {scenarioCount} scenarios which are faced by customers.
            Provide answer for each scenario by recording your response. You don't have to be too much technical
            regarding the problem. You can resubmit a response if something fails in first attempt. Press SUBMIT
            RESPONSE once all the responses have been recorded. All recorded answers will upload together when you
            press the final submit button.
          </p>
        </div>
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
          {submitting ? "Submitting..." : "Submit response"}
        </button>
        {error ? <p className="muted">{error}</p> : null}
      </div>
    </section>
  );
}
