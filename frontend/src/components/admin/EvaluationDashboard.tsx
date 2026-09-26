import { useCallback, useEffect, useState } from "react";
import "./EvaluationDashboard.css";

type SLOMetric = {
  name: string;
  target: number;
  actual: number;
  passed: boolean;
};

type EvaluationRun = {
  run_id: string;
  created_at: string;
  status: string;
  total_cases: number;
  overall_passed: boolean;
  metrics: SLOMetric[];
};

type EvaluationReport = {
  latest_run: EvaluationRun;
  historical_runs: EvaluationRun[];
  slo_metrics: SLOMetric[];
  case_count: number;
  cases: Record<string, unknown>[];
  generated_at: string;
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000";

const SLO_ORDER = [
  "Faithfulness",
  "Answer Relevancy",
  "Context Precision",
  "Context Recall",
  "Route Accuracy",
  "P95 Latency",
];

function formatMetric(
  metric: SLOMetric,
): string {
  if (metric.name === "P95 Latency") {
    return `${Number(metric.actual).toFixed(0)} ms`;
  }

  return `${Number(metric.actual).toFixed(1)}%`;
}

function formatTarget(
  metric: SLOMetric,
): string {
  if (metric.name === "P95 Latency") {
    return `≤ ${Number(metric.target).toFixed(0)} ms`;
  }

  return `≥ ${Number(metric.target).toFixed(1)}%`;
}

export default function EvaluationDashboard() {
  const [report, setReport] =
    useState<EvaluationReport | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const loadReport = useCallback(
    async () => {
      try {
        setLoading(true);
        setError(null);

        const token =
          localStorage.getItem("access_token") ||
          localStorage.getItem("token");

        const headers: HeadersInit = {
          Accept: "application/json",
        };

        if (token) {
          headers.Authorization =
            `Bearer ${token}`;
        }

        const response = await fetch(
          `${API_BASE_URL}/evaluation/report`,
          {
            method: "GET",
            headers,
          },
        );

        if (!response.ok) {
          const body =
            await response.text();

          throw new Error(
            body ||
              `Evaluation report failed: ${response.status}`,
          );
        }

        const data =
          (await response.json()) as EvaluationReport;

        setReport(data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load evaluation report.",
        );
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  if (loading) {
    return (
      <div className="evaluation-page">
        <div className="evaluation-loading">
          Loading SLO dashboard...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="evaluation-page">
        <div className="evaluation-header">
          <div>
            <h1>Evaluation & SLOs</h1>
            <p>
              ERIS production evaluation
            </p>
          </div>

          <button
            className="evaluation-refresh"
            onClick={() => void loadReport()}
          >
            Retry
          </button>
        </div>

        <div className="evaluation-error">
          <strong>
            Unable to load SLO report
          </strong>

          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!report) {
    return null;
  }

  const metricsByName =
    new Map(
      report.slo_metrics.map(
        (metric) => [
          metric.name,
          metric,
        ],
      ),
    );

  const orderedMetrics =
    SLO_ORDER
      .map(
        (name) =>
          metricsByName.get(name),
      )
      .filter(
        (
          metric,
        ): metric is SLOMetric =>
          Boolean(metric),
      );

  return (
    <div className="evaluation-page">
      <div className="evaluation-header">
        <div>
          <h1>
            Evaluation & SLOs
          </h1>

          <p>
            Six production SLOs for ERIS
          </p>
        </div>

        <button
          className="evaluation-refresh"
          onClick={() => void loadReport()}
        >
          Refresh
        </button>
      </div>

      <div className="evaluation-summary">
        <div className="summary-card">
          <span className="summary-label">
            Evaluation Status
          </span>

          <strong
            className={
              report.latest_run
                .overall_passed
                ? "status-pass"
                : "status-fail"
            }
          >
            {report.latest_run
              .overall_passed
              ? "All SLOs Passed"
              : "SLOs Need Attention"}
          </strong>
        </div>

        <div className="summary-card">
          <span className="summary-label">
            Cases
          </span>

          <strong>
            {report.case_count}
          </strong>
        </div>

        <div className="summary-card">
          <span className="summary-label">
            Run Status
          </span>

          <strong>
            {report.latest_run.status}
          </strong>
        </div>

        <div className="summary-card">
          <span className="summary-label">
            Last Updated
          </span>

          <strong>
            {new Date(
              report.generated_at,
            ).toLocaleString()}
          </strong>
        </div>
      </div>

      <section className="slo-section">
        <div className="section-title">
          <h2>
            Six SLOs
          </h2>

          <span>
            Latest evaluation run
          </span>
        </div>

        <div className="slo-grid">
          {orderedMetrics.map(
            (metric) => (
              <div
                key={metric.name}
                className={
                  metric.passed
                    ? "slo-card passed"
                    : "slo-card failed"
                }
              >
                <div className="slo-card-top">
                  <h3>
                    {metric.name}
                  </h3>

                  <span
                    className={
                      metric.passed
                        ? "slo-badge passed"
                        : "slo-badge failed"
                    }
                  >
                    {metric.passed
                      ? "PASS"
                      : "FAIL"}
                  </span>
                </div>

                <div className="slo-value">
                  {formatMetric(metric)}
                </div>

                <div className="slo-target">
                  Target{" "}
                  {formatTarget(metric)}
                </div>

                <div className="slo-progress">
                  <div
                    className="slo-progress-track"
                  >
                    <div
                      className="slo-progress-value"
                      style={{
                        width:
                          metric.name ===
                          "P95 Latency"
                            ? `${Math.min(
                                100,
                                (Number(
                                  metric.actual,
                                ) /
                                  Number(
                                    metric.target,
                                  )) *
                                  100,
                              )}%`
                            : `${Math.min(
                                100,
                                Number(
                                  metric.actual,
                                ),
                              )}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            ),
          )}
        </div>
      </section>

      <section className="evaluation-table-section">
        <div className="section-title">
          <h2>
            SLO Details
          </h2>
        </div>

        <div className="evaluation-table-wrapper">
          <table className="evaluation-table">
            <thead>
              <tr>
                <th>SLO</th>
                <th>Actual</th>
                <th>Target</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              {orderedMetrics.map(
                (metric) => (
                  <tr
                    key={metric.name}
                  >
                    <td>
                      {metric.name}
                    </td>

                    <td>
                      {formatMetric(metric)}
                    </td>

                    <td>
                      {formatTarget(metric)}
                    </td>

                    <td>
                      <span
                        className={
                          metric.passed
                            ? "table-status pass"
                            : "table-status fail"
                        }
                      >
                        {metric.passed
                          ? "PASS"
                          : "FAIL"}
                      </span>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="historical-section">
        <div className="section-title">
          <h2>
            Historical Runs
          </h2>
        </div>

        {report.historical_runs.length ===
        0 ? (
          <div className="empty-history">
            No previous evaluation runs.
          </div>
        ) : (
          <div className="evaluation-table-wrapper">
            <table className="evaluation-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Cases</th>
                  <th>Status</th>
                  <th>Overall</th>
                </tr>
              </thead>

              <tbody>
                {report.historical_runs.map(
                  (run) => (
                    <tr
                      key={run.run_id}
                    >
                      <td>
                        {new Date(
                          run.created_at,
                        ).toLocaleString()}
                      </td>

                      <td>
                        {run.total_cases}
                      </td>

                      <td>
                        {run.status}
                      </td>

                      <td>
                        <span
                          className={
                            run.overall_passed
                              ? "table-status pass"
                              : "table-status fail"
                          }
                        >
                          {run.overall_passed
                            ? "PASS"
                            : "FAIL"}
                        </span>
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}