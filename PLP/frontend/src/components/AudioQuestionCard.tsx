import { useEffect, useRef, useState } from "react";
import type { CandidateAnswerDetail } from "../types";

interface AudioQuestionCardProps {
  answer: CandidateAnswerDetail;
  uploading: boolean;
  onUpload: (questionId: string, file: File) => Promise<void>;
}

export function AudioQuestionCard({ answer, uploading, onUpload }: AudioQuestionCardProps) {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(answer.audio_url ?? null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    setPreviewUrl(answer.audio_url ?? null);
  }, [answer.audio_url]);

  useEffect(() => {
    return () => {
      if (previewUrl?.startsWith("blob:")) {
        URL.revokeObjectURL(previewUrl);
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [previewUrl]);

  async function startRecording() {
    try {
      setError(null);
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
        setPendingFile(file);
        if (previewUrl?.startsWith("blob:")) {
          URL.revokeObjectURL(previewUrl);
        }
        setPreviewUrl(URL.createObjectURL(blob));
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

  async function handleUpload() {
    if (!pendingFile) {
      return;
    }
    await onUpload(answer.question_id, pendingFile);
    setPendingFile(null);
  }

  return (
    <article className="question-card">
      <div className="question-top">
        <div>
          <div className="question-number">Q{answer.display_order}</div>
          <h3 className="section-title">{answer.question_title}</h3>
          <p className="muted">{answer.question_code}</p>
        </div>
        <span className={`status ${answer.audio_url ? "success" : "warning"}`}>
          {answer.audio_url ? "Recorded" : "Awaiting response"}
        </span>
      </div>

      <div>
        <p className="muted">Scenario audio</p>
        <audio controls src={answer.question_audio_url} style={{ width: "100%" }} />
      </div>

      <div className="record-strip">
        {!recording ? (
          <button className="primary-button" type="button" onClick={startRecording}>
            Start recording
          </button>
        ) : (
          <button className="secondary-button" type="button" onClick={stopRecording}>
            Stop recording
          </button>
        )}

        <span className={`status ${recording ? "warning" : "success"}`}>
          {recording ? "Recording live" : "Recorder idle"}
        </span>
      </div>

      {previewUrl ? (
        <div>
          <p className="muted">Candidate playback</p>
          <audio controls src={previewUrl} style={{ width: "100%" }} />
        </div>
      ) : null}

      <div className="record-strip">
        <button
          className="primary-button"
          type="button"
          disabled={!pendingFile || uploading}
          onClick={handleUpload}
        >
          {uploading ? "Uploading..." : "Upload response"}
        </button>
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
