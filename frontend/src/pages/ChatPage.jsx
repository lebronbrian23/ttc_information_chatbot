import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { chatApi } from "../api/chat";
import { useAuth } from "../context/AuthContext";
import MessageBubble from "../components/MessageBubble";
import FeedbackBar from "../components/FeedbackBar";
import styles from "./ChatPage.module.css";

const SUGGESTIONS = [
  "Will Line 1 be delayed at 5pm today?",
  "What's the delay chance on Line 2 on Monday morning?",
  "How often is the Bloor-Yonge station delayed?",
  "Is Line 4 usually delayed on weekends?",
];

export default function ChatPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "bot",
      text: "Hi! I'm the TTC Delay Prediction Chatbot. Ask me about subway delay probabilities on any line, station, day, or time.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to newest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      const userMsg = { id: Date.now(), role: "user", text: trimmed };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      // Reset textarea height
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
      }

      try {
        const { data } = await chatApi.sendMessage({
          message: trimmed,
          session_id: sessionId || undefined,
        });

        if (!sessionId && data.session_id) {
          setSessionId(data.session_id);
        }

        const botMsg = {
          id: Date.now() + 1,
          role: "bot",
          text: data.response,
          mlUsed: data.ml_used,
          predictionData: data.data,
        };
        setMessages((prev) => [...prev, botMsg]);

        // Show feedback bar after first real exchange
        setShowFeedback(true);
      } catch (err) {
        const detail = err.response?.data?.detail;
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: "bot",
            text:
              typeof detail === "string"
                ? detail
                : "Sorry, I couldn't process that. Please try again.",
            isError: true,
          },
        ]);
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    },
    [loading, sessionId]
  );

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  function handleInputChange(e) {
    const textarea = e.target;
    setInput(textarea.value);
    
    // Auto-grow textarea based on content
    textarea.style.height = "auto";
    const scrollHeight = textarea.scrollHeight;
    textarea.style.height = `${Math.min(scrollHeight, 280)}px`;
  }

  function handleNewChat() {
    setMessages([
      {
        id: "welcome",
        role: "bot",
        text: "Starting a new conversation. What would you like to know about TTC delays?",
      },
    ]);
    setSessionId(null);
    setShowFeedback(false);
    setInput("");
    
    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
    
    inputRef.current?.focus();
  }

  return (
    <div className={styles.layout}>
      {/* ── Sidebar ── */}
      <aside className={`${styles.sidebar} ${sidebarOpen ? styles.sidebarOpen : ""}`}>
        <div className={styles.sidebarHeader}>
          <span className={styles.sidebarLogo}>🚇</span>
          <span className={styles.sidebarTitle}>TTC Chatbot</span>
          <button
            className={styles.closeSidebarBtn}
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            ✕
          </button>
        </div>

        <button className={styles.newChatBtn} onClick={handleNewChat}>
          + New chat
        </button>

        <div className={styles.sidebarSection}>
          <p className={styles.sidebarSectionLabel}>Try asking</p>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              className={styles.suggestionBtn}
              onClick={() => sendMessage(s)}
            >
              {s}
            </button>
          ))}
        </div>

        <div className={styles.sidebarFooter}>
          {user ? (
            <>
              <p className={styles.sidebarUser}>
                Signed in as <strong>{user.username}</strong>
                {user.role === "admin" && (
                  <span className={styles.adminBadge}> admin</span>
                )}
              </p>
              <button
                className={styles.profileBtn}
                onClick={() => navigate("/profile")}
              >
                👤 Profile
              </button>
              <button
                className={styles.logoutBtn}
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
              >
                Sign out
              </button>
            </>
          ) : (
            <button
              className={styles.loginBtn}
              onClick={() => navigate("/login")}
            >
              Sign in
            </button>
          )}
        </div>
      </aside>

      {/* ── Sidebar Backdrop (mobile) ── */}
      {sidebarOpen && (
        <div
          className={styles.sidebarBackdrop}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Chat area ── */}
      <main className={styles.main}>
        {/* ── Hamburger Menu Button ── */}
        <button
          className={styles.hamburgerBtn}
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-label="Toggle sidebar"
        >
          ☰
        </button>

        <div className={styles.messages}>
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {loading && (
            <div className={styles.typingIndicator}>
              <span /><span /><span />
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {showFeedback && sessionId && (
          <FeedbackBar sessionId={sessionId} />
        )}

        <form
          className={styles.inputBar}
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input);
          }}
        >
          <textarea
            ref={inputRef}
            className={styles.textarea}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask about TTC delays… (Shift+Enter for newline, Enter to send)"
            rows={1}
            maxLength={5000}
          />
          <button
            className={styles.sendBtn}
            type="submit"
            disabled={loading || !input.trim()}
            aria-label="Send message"
          >
            ➤
          </button>
        </form>
      </main>
    </div>
  );
}
