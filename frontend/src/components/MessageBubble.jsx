import styles from "./MessageBubble.module.css";

/**
 * Renders a single chat message bubble.
 * @param {{ message: { role: 'user'|'bot', text: string, mlUsed?: boolean, predictionData?: object, isError?: boolean } }} props
 */
export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`${styles.wrapper} ${isUser ? styles.userWrapper : styles.botWrapper}`}>
      {!isUser && <span className={styles.avatar}>🚇</span>}
      <div
        className={`${styles.bubble} ${isUser ? styles.userBubble : styles.botBubble} ${message.isError ? styles.errorBubble : ""}`}
      >
        <p className={styles.text}>{message.text}</p>

        {/* Prediction data card */}
        {message.predictionData && (
          <PredictionCard data={message.predictionData} />
        )}

        {/* ML badge */}
        {message.mlUsed && (
          <span className={styles.mlBadge}>ML prediction</span>
        )}
      </div>
    </div>
  );
}

function PredictionCard({ data }) {
  if (!data || typeof data !== "object") return null;
  const entries = Object.entries(data).filter(
    ([, v]) => v !== null && v !== undefined
  );
  if (!entries.length) return null;

  return (
    <div className={styles.predCard}>
      {entries.map(([key, value]) => (
        <div key={key} className={styles.predRow}>
          <span className={styles.predKey}>{formatKey(key)}</span>
          <span className={styles.predVal}>{formatValue(key, value)}</span>
        </div>
      ))}
    </div>
  );
}

function formatKey(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatValue(key, value) {
  if (typeof value === "number") {
    // If looks like a probability/percentage
    if (key.includes("prob") || key.includes("chance") || key.includes("likelihood")) {
      return `${(value * 100).toFixed(1)}%`;
    }
    return value.toFixed(2);
  }
  return String(value);
}
