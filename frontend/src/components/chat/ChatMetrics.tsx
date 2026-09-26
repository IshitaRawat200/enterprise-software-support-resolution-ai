import "./ChatMetrics.css";

interface ChatMetricsProps {
  accuracy?: number | null;
  faithfulness?: number | null;
  answerRelevance?: number | null;
  contextPrecision?: number | null;
  contextRecall?: number | null;
  routeAccuracy?: number | null;
  guardrailEffectiveness?: number | null;
  costUsd?: number | null;
  latencyMs?: number | null;
}

function formatPercent(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "N/A";
  }

  const percentage = value >= 0 && value <= 1 ? value * 100 : value;
  return `${percentage.toFixed(1)}%`;
}

function formatCost(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "N/A";
  }

  return `$${value.toFixed(6)}`;
}

function formatLatency(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "N/A";
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}s`;
  }

  return `${value.toFixed(0)}ms`;
}

interface MetricItemProps {
  label: string;
  value: string;
}

function MetricItem({ label, value }: MetricItemProps) {
  return (
    <div className="chat-metric">
      <span className="chat-metric-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function ChatMetrics({
  accuracy,
  faithfulness,
  answerRelevance,
  contextPrecision,
  contextRecall,
  routeAccuracy,
  guardrailEffectiveness,
  costUsd,
  latencyMs,
}: ChatMetricsProps) {
  return (
    <section className="chat-metrics" aria-label="Response metrics">
      <div className="chat-metrics-title">Response Metrics</div>

      <div className="chat-metrics-grid chat-metrics-grid-primary">
        <MetricItem label="Accuracy" value={formatPercent(accuracy)} />
        <MetricItem
          label="Faithfulness"
          value={formatPercent(faithfulness)}
        />
        <MetricItem
          label="Answer Relevancy"
          value={formatPercent(answerRelevance)}
        />
        <MetricItem
          label="Context Precision"
          value={formatPercent(contextPrecision)}
        />
        <MetricItem
          label="Context Recall"
          value={formatPercent(contextRecall)}
        />
        <MetricItem
          label="Route Accuracy"
          value={formatPercent(routeAccuracy)}
        />
      </div>

      <div className="chat-metrics-grid chat-metrics-grid-secondary">
        <MetricItem
          label="Guardrail"
          value={formatPercent(guardrailEffectiveness)}
        />
        <MetricItem label="Cost" value={formatCost(costUsd)} />
        <MetricItem label="Latency" value={formatLatency(latencyMs)} />
      </div>
    </section>
  );
}
