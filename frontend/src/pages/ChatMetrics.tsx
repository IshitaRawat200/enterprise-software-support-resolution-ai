import type { ChatMetadata } from "./chatTypes";
import {
  formatCost,
  formatLatency,
  formatPercent,
} from "./chatHelpers";

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: "10px",
        background: "#ffffff",
        padding: "8px 10px",
        minHeight: "62px",
        height: "62px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        boxSizing: "border-box",
        minWidth: 0,
      }}
    >
      <div
        style={{
          fontSize: "10px",
          fontWeight: 400,
          color: "#64748b",
          lineHeight: 1.2,
          marginBottom: "4px",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {label}
      </div>

      <div
        style={{
          fontSize: "16px",
          fontWeight: 700,
          color: "#0f172a",
          lineHeight: 1.2,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {value}
      </div>
    </div>
  );
}

export default function ChatMetrics({
  metadata,
}: {
  metadata?: ChatMetadata;
}) {
  if (!metadata) {
    return null;
  }

  const evaluationPending =
    metadata.evaluation_status == null ||
    metadata.evaluation_status === "pending";

  const formatEvaluationPercent = (
    value: number | null | undefined,
  ): string => {
    if (evaluationPending && value == null) {
      return "Pending";
    }

    return formatPercent(value);
  };

  return (
    <div
      style={{
        marginTop: "12px",
        width: "100%",
      }}
    >
      <div
        style={{
          fontSize: "13px",
          fontWeight: 600,
          color: "#334155",
          marginBottom: "8px",
        }}
      >
        Response Metrics
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fit, minmax(105px, 1fr))",
          gap: "6px",
          width: "100%",
          maxWidth: "770px",
        }}
      >
        <MetricCard
          label="Accuracy"
          value={formatEvaluationPercent(metadata.accuracy)}
        />

        <MetricCard
          label="Faithfulness"
          value={formatEvaluationPercent(metadata.faithfulness)}
        />

        <MetricCard
          label="Answer Relevancy"
          value={formatEvaluationPercent(metadata.answer_relevance)}
        />

        <MetricCard
          label="Context Precision"
          value={formatEvaluationPercent(metadata.context_precision)}
        />

        <MetricCard
          label="Context Recall"
          value={formatEvaluationPercent(metadata.context_recall)}
        />

        <MetricCard
          label="Route Accuracy"
          value={formatPercent(
            metadata.route_accuracy,
          )}
        />

        <MetricCard
          label="Guardrail"
          value={formatPercent(
            metadata.guardrail_effectiveness,
          )}
        />

        <MetricCard
          label="Cost"
          value={formatCost(
            metadata.cost_usd,
          )}
        />

        <MetricCard
          label="Latency"
          value={formatLatency(
            metadata.latency_ms,
          )}
        />
      </div>

      {evaluationPending && (
        <div
          style={{
            marginTop: "6px",
            fontSize: "10px",
            color: "#64748b",
          }}
        >
          Evaluation in progress…
        </div>
      )}
    </div>
  );
}
