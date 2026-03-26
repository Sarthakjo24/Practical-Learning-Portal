import { Link, useParams } from "react-router-dom";

export function SubmissionSuccessPage() {
  const { sessionId } = useParams();

  return (
    <section className="dashboard-grid">
      <div className="panel">
        <h1 className="page-title">Responses submitted successfully</h1>
        <p className="muted">
          Your recordings have entered the background evaluation pipeline. No score is shown in the
          candidate experience.
        </p>
        <div className="badge-row">
          <span className="pill">{sessionId}</span>
          <span className="pill">Processing in background</span>
        </div>
        <div className="spacer" />
        <Link className="primary-button" to="/dashboard">
          Return to dashboard
        </Link>
      </div>
    </section>
  );
}
