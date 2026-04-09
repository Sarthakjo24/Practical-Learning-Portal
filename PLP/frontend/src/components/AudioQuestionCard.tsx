import { useEffect, useRef, useState } from "react";
import type { CandidateAnswerDetail } from "../types";

interface AudioQuestionCardProps {
  answer: CandidateAnswerDetail;
  pendingFile: File | null;
  onRecordingReady: (questionId: string, file: File) => void;
}

export function AudioQuestionCard({ answer, pendingFile, onRecordingReady }: AudioQuestionCardProps) {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(answer.audio_url ?? null);
  const [resubmitAttemptsUsed, setResubmitAttemptsUsed] = useState(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const replacementAttemptRef = useRef(false);
  const hasExistingResponse = Boolean(answer.audio_url || pendingFile);
  const isResubmitExhausted = hasExistingResponse && resubmitAttemptsUsed >= 1;

  useEffect(() => {
    if (pendingFile) {
      const nextPreviewUrl = URL.createObjectURL(pendingFile);
      setPreviewUrl((current) => {
        if (current?.startsWith("blob:")) {
          URL.revokeObjectURL(current);
        }
        return nextPreviewUrl;
      });
      return () => {
        URL.revokeObjectURL(nextPreviewUrl);
      };
    }

    setPreviewUrl(answer.audio_url ?? null);
    return undefined;
  }, [answer.audio_url, pendingFile]);

  useEffect(() => {
    return () => {
      if (previewUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(previewUrl);
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [previewUrl]);

  async function startRecording() {
    if (isResubmitExhausted) {
      setError("resubmit attempts exhausted");
      return;
    }

    try {
      setError(null);
      replacementAttemptRef.current = hasExistingResponse;

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const file = new File([blob], `${answer.question_code}.webm`, { type: "audio/webm" });
        onRecordingReady(answer.question_id, file);
        if (replacementAttemptRef.current) {
          setResubmitAttemptsUsed(1);
        }
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start();
      setRecording(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Microphone access failed.");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  return (
    <article className="question-card">
      <div className="question-top">
        <div>
          <div className="question-number">Q{answer.display_order}</div>
          <h3 className="section-title">{answer.question_title}</h3>
          <p className="muted">{answer.question_code}</p>
        </div>
        {hasExistingResponse ? <span className="status success">Recorded</span> : <span className="status warning">Awaiting response</span>}
      </div>

      <div>
        <p className="muted">Scenario audio</p>
        <audio
          controls
          controlsList="nodownload"
          onContextMenu={(event) => event.preventDefault()}
          src={answer.question_audio_url}
          style={{ width: "100%" }}
        />
      </div>

      <div className="record-strip">
        {!recording ? (
          <button className="primary-button" type="button" onClick={startRecording} disabled={isResubmitExhausted}>
            {hasExistingResponse ? "Record replacement" : "Start recording"}
          </button>
        ) : (
          <button className="secondary-button" type="button" onClick={stopRecording}>
            Stop recording
          </button>
        )}
      </div>

      {previewUrl ? (
        <div>
          <p className="muted">Candidate playback</p>
          <audio
            controls
            controlsList="nodownload"
            onContextMenu={(event) => event.preventDefault()}
            src={previewUrl}
            style={{ width: "100%" }}
          />
        </div>
      ) : null}

      <div className="record-strip">
        {isResubmitExhausted ? <span className="status warning">resubmit attempts exhausted</span> : null}
        {answer.transcript_text ? <span className="status success">Processed</span> : null}
      </div>

      {answer.transcript_text ? (
        <div className="module-card">
          <strong>Transcript</strong>
          <p className="muted">{answer.transcript_text}</p>
        </div>
      ) : null}

      {error ? <p className="muted">{error}</p> : null}
    </article>
  );
}
