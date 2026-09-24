import { useEffect, useState } from "react";
import {
  getEvaluationReport,
  type EvaluationReport,
  type SLOMetric,
} from "../../services/adminApi";
import "./EvaluationDashboard.css";

function formatMetricName(
  name: string
): string {
  return name
    .replace(/_percent$/i, "")
    .replace(/_ms$/i, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase()
    );
}

function formatMetricValue(
  metric: SLOMetric
): string {
  if (metric.name.includes("latency")) {
    return `${Number(metric.value).toFixed(0)} ms`;
  }

  if (metric.name.includes("cost")) {
    return `$${Number(metric.value).toFixed(4)}`;
  }

  if (metric.name.includes("violations")) {
    return String(metric.value);
  }

  return `${Number(metric.value).toFixed(2)}%`;
}

function formatTarget(
  metric: SLOMetric
): string {
  if (metric.name.includes("latency")) {
    return `≤ ${Number(metric.target).toFixed(0)} ms`;
  }

  if (metric.name.includes("cost")) {
    return `≤ $${Number(metric.target).toFixed(4)}`;
  }

  if (metric.name.includes("violations")) {
    return `≤ ${Number(metric.target)}`;
  }

  return `≥ ${Number(metric.target).toFixed(2)}%`;
}

export default function EvaluationDashboard() {
  const [report, setReport] =
    useState<EvaluationReport | null>(
      null
    );

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  async function loadReport() {
    try {
      setLoading(true);
      setError("");

      const data =
        await getEvaluationReport();

      setReport(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load evaluation report."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadReport();
  }, []);

  if (loading) {
    return (
      <section className="evaluation-dashboard">
        <div className="evaluation-empty">
          Loading evaluation results...
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="evaluation-dashboard">
        <div className="evaluation-message error">
          {error}
        </div>
      </section>
    );
  }

  if (!report) {
    return (
      <section className="evaluation-dashboard">
        <div className="evaluation-empty">
          No evaluation results available.
        </div>
      </section>
    );
  }

  const sloMetrics =
    report.slo_metrics ?? [];

  const cases =
    report.cases ?? [];

  const overallPassed =
    report.overall_slo_passed ??
    report.overall_passed ??
    false;

  return (
    <section className="evaluation-dashboard">
      <div className="evaluation-header">
        <div>
          <h2>Evaluation Dashboard</h2>

          <p>
            ERIS Golden Dataset evaluation
            and SLO performance.
          </p>
        </div>

        <button
          type="button"
          className="evaluation-refresh-button"
          onClick={() =>
            void loadReport()
          }
        >
          Refresh
        </button>
      </div>

      <div className="evaluation-summary">
        <div className="evaluation-summary-card">
          <span>Run Status</span>

          <strong>
            {report.status}
          </strong>
        </div>

        <div className="evaluation-summary-card">
          <span>Total Cases</span>

          <strong>
            {report.total_cases}
          </strong>
        </div>

        <div className="evaluation-summary-card">
          <span>Overall SLO</span>

          <strong
            className={
              overallPassed
                ? "evaluation-pass"
                : "evaluation-fail"
            }
          >
            {overallPassed
              ? "PASSED"
              : "FAILED"}
          </strong>
        </div>

        <div className="evaluation-summary-card">
          <span>Run Date</span>

          <strong>
            {new Date(
              report.created_at
            ).toLocaleString()}
          </strong>
        </div>
      </div>

      <div className="evaluation-card">
        <div className="evaluation-card-header">
          <h3>SLO Results</h3>
        </div>

        {sloMetrics.length === 0 ? (
          <div className="evaluation-empty">
            No SLO metrics available for
            this evaluation run.
          </div>
        ) : (
          <div className="evaluation-table-wrapper">
            <table className="evaluation-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Actual</th>
                  <th>Target</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {sloMetrics.map(
                  (metric) => (
                    <tr
                      key={metric.name}
                    >
                      <td>
                        {formatMetricName(
                          metric.name
                        )}
                      </td>

                      <td>
                        {formatMetricValue(
                          metric
                        )}
                      </td>

                      <td>
                        {formatTarget(
                          metric
                        )}
                      </td>

                      <td>
                        <span
                          className={`evaluation-status ${
                            metric.passed
                              ? "pass"
                              : "fail"
                          }`}
                        >
                          {metric.passed
                            ? "PASS"
                            : "FAIL"}
                        </span>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="evaluation-card evaluation-cases-card">
        <div className="evaluation-card-header">
          <h3>Evaluation Cases</h3>

          <span>
            {report.total_cases} cases
          </span>
        </div>

        {cases.length === 0 ? (
          <div className="evaluation-empty">
            No evaluation cases available.
          </div>
        ) : (
          <div className="evaluation-table-wrapper">
            <table className="evaluation-table">
              <thead>
                <tr>
                  <th>Test ID</th>
                  <th>Query</th>
                  <th>Expected Route</th>
                  <th>Actual Route</th>
                  <th>Result</th>
                </tr>
              </thead>

              <tbody>
                {cases.map(
                  (testCase, index) => {
                    const item =
                      testCase as Record<
                        string,
                        unknown
                      >;

                    const testId =
                      item.test_id ??
                      item.case_id ??
                      item.id ??
                      `Case ${index + 1}`;

                    const query =
                      item.query ??
                      item.question ??
                      "";

                    const expectedRoute =
                      item.expected_route ??
                      "";

                    const actualRoute =
                      item.actual_route ??
                      "";

                    const passed =
                      item.passed ??
                      item.success ??
                      item.evaluation_passed;

                    return (
                      <tr
                        key={`${String(
                          testId
                        )}-${index}`}
                      >
                        <td>
                          {String(
                            testId
                          )}
                        </td>

                        <td className="evaluation-query">
                          {String(query)}
                        </td>

                        <td>
                          {String(
                            expectedRoute
                          )}
                        </td>

                        <td>
                          {String(
                            actualRoute
                          )}
                        </td>

                        <td>
                          {typeof passed ===
                          "boolean" ? (
                            <span
                              className={`evaluation-status ${
                                passed
                                  ? "pass"
                                  : "fail"
                              }`}
                            >
                              {passed
                                ? "PASS"
                                : "FAIL"}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    );
                  }
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}