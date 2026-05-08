import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import styles from "./Auth.module.css";

function getFriendlyLoginMessage(message) {
  if (!message) {
    return "Login failed. Please try again.";
  }
  if (message.includes("Invalid username")) {
    return "Invalid username.";
  }
  if (message.includes("Invalid password")) {
    return "Invalid password.";
  }
  if (message.includes("Invalid username or password")) {
    return "Invalid username or password.";
  }
  if (message.includes("Account is inactive")) {
    return "Your account is inactive. Contact an administrator.";
  }
  if (message.includes("Account is not verified")) {
    return "Your account is not verified yet. Please verify your email or contact support.";
  }
  if (message.includes("String should have at least 3 characters")) {
    return "Username must be at least 3 characters long.";
  }
  return message;
}

function buildLoginErrors(err) {
  const fieldErrors = {};
  let formError = "";
  const payload = err?.response?.data;
  const detail = payload?.detail;

  if (Array.isArray(detail)) {
    detail.forEach((item) => {
      const field = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : item?.loc;
      const msg = getFriendlyLoginMessage(item?.msg || "");
      if (field === "username" || field === "password") {
        fieldErrors[field] = msg;
      } else if (!formError) {
        formError = msg;
      }
    });
    return { fieldErrors, formError };
  }

  if (typeof detail === "string") {
    const msg = getFriendlyLoginMessage(detail);
    if (msg === "Invalid username or password." || msg === "Invalid password.") {
      fieldErrors.password = msg;
    } else if (msg === "Invalid username.") {
      fieldErrors.username = msg;
    } else {
      formError = msg;
    }
    return { fieldErrors, formError };
  }

  if (!err?.response) {
    if (err?.code === "ECONNABORTED") {
      formError = "Login request timed out. Please try again.";
    } else {
      formError = "Cannot reach the server. Please ensure the backend is running.";
    }
    return { fieldErrors, formError };
  }

  if (typeof payload?.message === "string") {
    formError = getFriendlyLoginMessage(payload.message);
    return { fieldErrors, formError };
  }

  if (typeof payload?.error === "string") {
    formError = getFriendlyLoginMessage(payload.error);
    return { fieldErrors, formError };
  }

  formError = "Login failed. Please try again.";
  return { fieldErrors, formError };
}

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({ username: "", password: "" });
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setFieldErrors((prev) => {
      if (!prev[name]) return prev;
      return { ...prev, [name]: "" };
    });
    setFormError("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFieldErrors({});
    setFormError("");
    setLoading(true);
    try {
      const { data } = await authApi.login(form);
      login(data);
      navigate("/chat");
    } catch (err) {
      const { fieldErrors: nextFieldErrors, formError: nextFormError } = buildLoginErrors(err);
      setFieldErrors(nextFieldErrors);
      setFormError(nextFormError);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>🚇</span>
          <h1 className={styles.logoText}>TTC Chatbot</h1>
        </div>

        <h2 className={styles.title}>Sign in</h2>

        <form onSubmit={handleSubmit} className={styles.form}>
          <label className={styles.label}>
            Username
            <input
              className={`${styles.input} ${fieldErrors.username ? styles.inputError : ""}`}
              type="text"
              name="username"
              value={form.username}
              onChange={handleChange}
              autoComplete="username"
              required
              aria-invalid={Boolean(fieldErrors.username)}
            />
            {fieldErrors.username && <p className={styles.fieldError}>{fieldErrors.username}</p>}
          </label>

          <label className={styles.label}>
            Password
            <div className={styles.passwordField}>
              <input
                className={`${styles.input} ${fieldErrors.password ? styles.inputError : ""}`}
                type={showPassword ? "text" : "password"}
                name="password"
                value={form.password}
                onChange={handleChange}
                autoComplete="current-password"
                required
                aria-invalid={Boolean(fieldErrors.password)}
              />
              <button
                className={styles.toggleBtn}
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
            {fieldErrors.password && <p className={styles.fieldError}>{fieldErrors.password}</p>}
          </label>

          {formError && <p className={styles.error}>{formError}</p>}

          <button className={styles.btn} type="submit" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className={styles.switchLink}>
          Don&apos;t have an account?{" "}
          <Link to="/register">Register</Link>
        </p>

        <p className={styles.switchLink}>
          <Link to="/chat">Continue as guest →</Link>
        </p>
      </div>
    </div>
  );
}
