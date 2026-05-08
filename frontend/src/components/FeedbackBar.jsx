import { useState } from "react";
import { chatApi } from "../api/chat";
import styles from "./FeedbackBar.module.css";

/**
 * Star-rating feedback bar shown after the first bot reply.
 * Sends rating to POST /api/sessions/:id/feedback
 */
export default function FeedbackBar({ sessionId }) {
  const [selected, setSelected] = useState(0);
  const [submitted, setSubmitted] = useState(false);

  async function handleRate(score) {
    if (submitted) return;
    setSelected(score);
    try {
      await chatApi.submitFeedback(sessionId, { feedback_score: score });
      setSubmitted(true);
    } catch {
      // Non-critical — swallow silently
    }
  }

  if (submitted) {
    return (
      <div className={styles.bar}>
        <span className={styles.thanks}>Thanks for your feedback!</span>
      </div>
    );
  }

  return (
    <div className={styles.bar}>
      <span className={styles.label}>Rate this conversation:</span>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          className={`${styles.star} ${n <= selected ? styles.filled : ""}`}
          onClick={() => handleRate(n)}
          aria-label={`Rate ${n} out of 5`}
        >
          ★
        </button>
      ))}
    </div>
  );
}
