import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import styles from "./Auth.module.css";

const PASSWORD_RULES = [
  {
    key: "minLength",
    label: "Min 8 chars",
    test: (password) => password.length >= 8,
  },
  {
    key: "uppercase",
    label: "Uppercase",
    test: (password) => /[A-Z]/.test(password),
  },
  {
    key: "lowercase",
    label: "Lowercase",
    test: (password) => /[a-z]/.test(password),
  },
  {
    key: "digit",
    label: "Digit",
    test: (password) => /\d/.test(password),
  },
  {
    key: "special",
    label: "Special character",
    test: (password) => /[!@#$%^&*(),.?\":{}|<>]/.test(password),
  },
];

function getFriendlyValidationMessage(message) {
  if (message.includes("Username already registered")) {
    return "This username is already taken. Try another one.";
  }
  if (message.includes("Email already registered")) {
    return "This email is already registered. Try signing in instead.";
  }
  if (message.includes("Username or email already registered")) {
    return "That username or email is already registered.";
  }
  if (message.includes("String should match pattern '^[a-zA-Z0-9_-]+$'")) {
    return "Username can only include letters, numbers, underscores, and hyphens.";
  }
  if (message.includes("value is not a valid email address") || message.includes("valid email address")) {
    return "Enter a valid email address.";
  }
  if (message.includes("String should have at least 3 characters")) {
    return "Username must be at least 3 characters long.";
  }
  if (message.includes("String should have at most 255 characters")) {
    return "This value must be 255 characters or fewer.";
  }
  if (message.includes("Field required")) {
    return "Please fill in all required fields.";
  }
  if (message.includes("Password must contain at least one uppercase letter")) {
    return "Password needs at least one uppercase letter.";
  }
  if (message.includes("Password must contain at least one lowercase letter")) {
    return "Password needs at least one lowercase letter.";
  }
  if (message.includes("Password must contain at least one digit")) {
    return "Password needs at least one number.";
  }
  if (message.includes("Password must contain at least one special character")) {
    return "Password needs at least one special character.";
  }
  if (message.includes("String should have at least 8 characters")) {
    return "Password must be at least 8 characters long.";
  }
  return message;
}

function getFieldLabel(loc) {
  const fieldName = Array.isArray(loc) ? loc[loc.length - 1] : loc;
  const labels = {
    username: "Username",
    email: "Email",
    password: "Password",
    full_name: "Full name",
  };

  return labels[fieldName] || "Field";
}

function buildRegisterErrors(detail) {
  const fieldErrors = {};
  let formError = "";

  if (Array.isArray(detail)) {
    for (const item of detail) {
      if (!item) {
        continue;
      }

      const message = getFriendlyValidationMessage(item.msg || "");
      const fieldName = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : item.loc;
      const fieldLabel = getFieldLabel(item.loc);

      let finalMessage = message;
      if (message === "Please fill in all required fields.") {
        finalMessage = `${fieldLabel} is required.`;
      }

      if (["username", "email", "password", "full_name"].includes(fieldName)) {
        fieldErrors[fieldName] = finalMessage;
      } else if (!formError) {
        formError = finalMessage;
      }
    }

    return { fieldErrors, formError };
  }

  if (detail && typeof detail === "object") {
    if (typeof detail.message === "string") {
      formError = getFriendlyValidationMessage(detail.message);
      return { fieldErrors, formError };
    }

    if (typeof detail.error === "string") {
      formError = getFriendlyValidationMessage(detail.error);
      return { fieldErrors, formError };
    }
  }

  if (typeof detail === "string" && detail.trim()) {
    const message = getFriendlyValidationMessage(detail);

    if (detail.includes("Username or email already registered")) {
      fieldErrors.username = "This username may already be taken. Try another one.";
      fieldErrors.email = "This email may already be registered. Try another one or sign in.";
      return { fieldErrors, formError };
    }

    if (detail.includes("Username already registered")) {
      fieldErrors.username = "This username is already taken. Try another one.";
      return { fieldErrors, formError };
    }

    if (detail.includes("Email already registered")) {
      fieldErrors.email = "This email is already registered. Try signing in instead.";
      return { fieldErrors, formError };
    }

    formError = message;
    return { fieldErrors, formError };
  }

  return {
    fieldErrors,
    formError: "We couldn't create your account. Please try again in a moment.",
  };
}

function extractApiErrorDetail(err) {
  const payload = err?.response?.data;

  if (payload?.detail !== undefined) {
    return payload.detail;
  }

  if (payload?.message) {
    return payload.message;
  }

  if (payload?.error) {
    return payload.error;
  }

  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }

  return undefined;
}

function getGenericRequestMessage(err) {
  if (!err?.response) {
    if (err?.code === "ECONNABORTED") {
      return "The request timed out. Please try again.";
    }
    return "Cannot reach the server right now. Please check that the backend is running.";
  }

  const status = err.response.status;
  if (status >= 500) {
    return "Server error while creating your account. Please try again in a moment.";
  }

  return "We couldn't create your account. Please check your details and try again.";
}

export default function RegisterPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    full_name: "",
  });
  const [formError, setFormError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const passwordChecks = PASSWORD_RULES.map((rule) => ({
    ...rule,
    passed: rule.test(form.password),
  }));

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setFieldErrors((prev) => {
      if (!prev[name]) {
        return prev;
      }

      return { ...prev, [name]: "" };
    });
    setFormError("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    setFieldErrors({});
    setLoading(true);

    try {
      await authApi.register(form);
    } catch (err) {
      const detail = extractApiErrorDetail(err);
      const { fieldErrors: nextFieldErrors, formError: nextFormError } = buildRegisterErrors(detail);

      setFieldErrors(nextFieldErrors);
      setFormError(nextFormError || getGenericRequestMessage(err));
      setLoading(false);
      return;
    }

    try {
      // Auto-login after successful registration
      const { data } = await authApi.login({
        username: form.username,
        password: form.password,
      });
      login(data);
      navigate("/chat");
    } catch (err) {
      const detail = extractApiErrorDetail(err);
      const genericError = getGenericRequestMessage(err);
      const readable =
        typeof detail === "string" && detail.trim()
          ? getFriendlyValidationMessage(detail)
          : genericError;

      setFormError(
        `Your account was created, but automatic sign-in failed. ${readable} Please sign in from the login page.`
      );
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

        <h2 className={styles.title}>Create account</h2>

        <form onSubmit={handleSubmit} className={styles.form}>
          <label className={styles.label}>
            Full name (optional)
            <input
              className={`${styles.input} ${fieldErrors.full_name ? styles.inputError : ""}`}
              type="text"
              name="full_name"
              value={form.full_name}
              onChange={handleChange}
              autoComplete="name"
              aria-invalid={Boolean(fieldErrors.full_name)}
            />
            {fieldErrors.full_name && <p className={styles.fieldError}>{fieldErrors.full_name}</p>}
          </label>

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
            Email
            <input
              className={`${styles.input} ${fieldErrors.email ? styles.inputError : ""}`}
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              autoComplete="email"
              required
              aria-invalid={Boolean(fieldErrors.email)}
            />
            {fieldErrors.email && <p className={styles.fieldError}>{fieldErrors.email}</p>}
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
                autoComplete="new-password"
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
            <div className={styles.hintList}>
              {passwordChecks.map((rule) => (
                <span
                  key={rule.key}
                  className={`${styles.hint} ${rule.passed ? styles.hintSuccess : ""}`}
                >
                  {rule.label}
                </span>
              ))}
            </div>
            {fieldErrors.password && <p className={styles.fieldError}>{fieldErrors.password}</p>}
          </label>

          {formError && <p className={styles.error}>{formError}</p>}

          <button className={styles.btn} type="submit" disabled={loading}>
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className={styles.switchLink}>
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
