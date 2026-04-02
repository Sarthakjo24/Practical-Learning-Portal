import { useParams } from "react-router-dom";

export function SubmissionSuccessPage() {
  void useParams();

  return (
    <section className="dashboard-grid">
      <div className="panel">
        <h1 className="page-title">thank you for the response , our team will connect with you via email for further process</h1>
      </div>
    </section>
  );
}
