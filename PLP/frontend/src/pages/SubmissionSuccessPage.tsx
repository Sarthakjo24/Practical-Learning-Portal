import { useEffect } from "react";
import { useParams } from "react-router-dom";

export function SubmissionSuccessPage() {
  const { sessionId } = useParams();

  useEffect(() => {
    document.title = "Submission Complete";
  }, []);

  return (
    <section className="dashboard-grid">
      <div className="panel">
        <h1 className="page-title">THANK YOU !! YOUR TEST HAS BEEN SUBMITTED SUCCESSFULLY.</h1>
        <p className="muted">SCORES WILL BE SHARED TO YOU LATER.</p>
        {sessionId ? <p className="muted">Session ID: {sessionId}</p> : null}
      </div>
    </section>
  );
}
