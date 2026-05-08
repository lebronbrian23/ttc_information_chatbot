import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import styles from "./Profile.module.css";

function formatDate(date) {
  if (!date) return "Never";
  return new Date(date).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user: authUser } = useAuth();
  
  // Profile data
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Edit full name form
  const [isEditingName, setIsEditingName] = useState(false);
  const [editFullName, setEditFullName] = useState("");
  const [saveNameLoading, setSaveNameLoading] = useState(false);
  const [nameError, setNameError] = useState("");
  const [nameSuccess, setNameSuccess] = useState("");

  // Password form
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    old_password: "",
    new_password: "",
    confirm_password: "",
  });
  const [showPasswords, setShowPasswords] = useState({
    old: false,
    new: false,
    confirm: false,
  });
  const [changePasswordLoading, setChangePasswordLoading] = useState(false);
  const [passwordFormError, setPasswordFormError] = useState("");
  const [passwordFieldErrors, setPasswordFieldErrors] = useState({});
  const [passwordSuccess, setPasswordSuccess] = useState("");

  // Password validation rules
  const [passwordRules, setPasswordRules] = useState({
    hasUppercase: false,
    hasLowercase: false,
    hasDigit: false,
    hasSpecial: false,
    hasMinLength: false,
  });

  // Fetch current user on mount
  useEffect(() => {
    if (!authUser) {
      navigate("/login");
      return;
    }

    async function fetchUserProfile() {
      try {
        setLoading(true);
        setError("");
        const { data } = await authApi.getMe();
        setUser(data);
        setEditFullName(data.full_name || "");
      } catch (err) {
        setError("Failed to load profile. Please try again.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    fetchUserProfile();
  }, [authUser, navigate]);

  // Update password validation rules
  useEffect(() => {
    const pwd = passwordForm.new_password;
    setPasswordRules({
      hasUppercase: /[A-Z]/.test(pwd),
      hasLowercase: /[a-z]/.test(pwd),
      hasDigit: /\d/.test(pwd),
      hasSpecial: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>?/]/.test(pwd),
      hasMinLength: pwd.length >= 8,
    });
  }, [passwordForm.new_password]);

  // Handle full name edit
  function handleStartEditName() {
    setIsEditingName(true);
    setEditFullName(user?.full_name || "");
    setNameError("");
    setNameSuccess("");
  }

  function handleCancelEditName() {
    setIsEditingName(false);
    setEditFullName("");
    setNameError("");
  }

  async function handleSaveFullName() {
    setNameError("");
    setNameSuccess("");

    if (!editFullName.trim()) {
      setNameError("Full name cannot be empty");
      return;
    }

    try {
      setSaveNameLoading(true);
      const { data } = await authApi.updateMe(editFullName);
      setUser(data);
      setIsEditingName(false);
      setNameSuccess("Full name updated successfully!");
      setTimeout(() => setNameSuccess(""), 3000);
    } catch (err) {
      const errorMsg =
        err?.response?.data?.detail || "Failed to update full name";
      setNameError(errorMsg);
    } finally {
      setSaveNameLoading(false);
    }
  }

  // Handle password change form
  function handlePasswordFormChange(e) {
    const { name, value } = e.target;
    setPasswordForm((prev) => ({ ...prev, [name]: value }));
    setPasswordFieldErrors((prev) => {
      if (!prev[name]) return prev;
      return { ...prev, [name]: "" };
    });
    setPasswordFormError("");
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    setPasswordFieldErrors({});
    setPasswordFormError("");

    // Validation
    if (!passwordForm.old_password) {
      setPasswordFieldErrors((prev) => ({
        ...prev,
        old_password: "Current password is required",
      }));
      return;
    }

    if (!passwordForm.new_password) {
      setPasswordFieldErrors((prev) => ({
        ...prev,
        new_password: "New password is required",
      }));
      return;
    }

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordFieldErrors((prev) => ({
        ...prev,
        confirm_password: "Passwords do not match",
      }));
      return;
    }

    // Check all rules
    const allRulesMet = Object.values(passwordRules).every((rule) => rule);
    if (!allRulesMet) {
      setPasswordFormError(
        "Password does not meet all requirements. Check the rules below."
      );
      return;
    }

    try {
      setChangePasswordLoading(true);
      await authApi.resetPassword(
        passwordForm.old_password,
        passwordForm.new_password
      );
      setPasswordSuccess("Password changed successfully!");
      setPasswordForm({
        old_password: "",
        new_password: "",
        confirm_password: "",
      });
      setIsChangingPassword(false);
      setTimeout(() => setPasswordSuccess(""), 3000);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === "string") {
        if (detail.includes("Old password is incorrect")) {
          setPasswordFieldErrors((prev) => ({
            ...prev,
            old_password: "Current password is incorrect",
          }));
        } else {
          setPasswordFormError(detail);
        }
      } else {
        setPasswordFormError("Failed to change password. Please try again.");
      }
    } finally {
      setChangePasswordLoading(false);
    }
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.container}>
          <div className={styles.loading}>Loading profile...</div>
        </div>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className={styles.page}>
        <div className={styles.container}>
          <div className={styles.errorBanner}>{error || "User not found"}</div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <div className={styles.header}>
          <button className={styles.backButton} onClick={() => navigate("/chat")}>
            ← Back to Chat
          </button>
          <h1>Profile</h1>
        </div>

        {/* Profile Information */}
        <section className={styles.section}>
          <h2>Account Information</h2>

          {/* Display Fields */}
          <div className={styles.infoGrid}>
            <div className={styles.infoField}>
              <label>Username</label>
              <p className={styles.infoValue}>{user.username}</p>
            </div>

            <div className={styles.infoField}>
              <label>Email</label>
              <p className={styles.infoValue}>{user.email}</p>
            </div>

            <div className={styles.infoField}>
              <label>Role</label>
              <p className={styles.infoValue}>
                {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
              </p>
            </div>

            <div className={styles.infoField}>
              <label>Status</label>
              <p className={styles.infoValue}>
                {user.is_active ? "✓ Active" : "Inactive"}
              </p>
            </div>

            <div className={styles.infoField}>
              <label>Verification</label>
              <p className={styles.infoValue}>
                {user.is_verified ? "✓ Verified" : "Not verified"}
              </p>
            </div>

            <div className={styles.infoField}>
              <label>Member Since</label>
              <p className={styles.infoValue}>{formatDate(user.created_at)}</p>
            </div>

            <div className={styles.infoField}>
              <label>Last Login</label>
              <p className={styles.infoValue}>{formatDate(user.last_login)}</p>
            </div>
          </div>
        </section>

        {/* Edit Full Name */}
        <section className={styles.section}>
          <h2>Edit Profile</h2>

          {nameSuccess && <div className={styles.successBanner}>{nameSuccess}</div>}
          {nameError && <div className={styles.errorBanner}>{nameError}</div>}

          {!isEditingName ? (
            <div className={styles.editableField}>
              <label>Full Name</label>
              <div className={styles.editableDisplay}>
                <p>{user.full_name || "(Not set)"}</p>
                <button
                  type="button"
                  className={styles.editButton}
                  onClick={handleStartEditName}
                >
                  Edit
                </button>
              </div>
            </div>
          ) : (
            <div className={styles.editForm}>
              <label>Full Name</label>
              <input
                type="text"
                value={editFullName}
                onChange={(e) => setEditFullName(e.target.value)}
                placeholder="Enter your full name"
                className={styles.input}
              />
              <div className={styles.buttonGroup}>
                <button
                  type="button"
                  className={styles.primaryButton}
                  onClick={handleSaveFullName}
                  disabled={saveNameLoading}
                >
                  {saveNameLoading ? "Saving..." : "Save"}
                </button>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={handleCancelEditName}
                  disabled={saveNameLoading}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>

        {/* Change Password */}
        <section className={styles.section}>
          <h2>Security</h2>

          {passwordSuccess && (
            <div className={styles.successBanner}>{passwordSuccess}</div>
          )}

          {!isChangingPassword ? (
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() => setIsChangingPassword(true)}
            >
              Change Password
            </button>
          ) : (
            <form onSubmit={handleChangePassword} className={styles.passwordForm}>
              {passwordFormError && (
                <div className={styles.errorBanner}>{passwordFormError}</div>
              )}

              <label className={styles.label}>
                Current Password
                <div className={styles.passwordField}>
                  <input
                    className={`${styles.input} ${
                      passwordFieldErrors.old_password ? styles.inputError : ""
                    }`}
                    type={showPasswords.old ? "text" : "password"}
                    name="old_password"
                    value={passwordForm.old_password}
                    onChange={handlePasswordFormChange}
                    required
                    aria-invalid={Boolean(passwordFieldErrors.old_password)}
                  />
                  <button
                    type="button"
                    className={styles.toggleButton}
                    onClick={() =>
                      setShowPasswords((prev) => ({
                        ...prev,
                        old: !prev.old,
                      }))
                    }
                  >
                    {showPasswords.old ? "Hide" : "Show"}
                  </button>
                </div>
                {passwordFieldErrors.old_password && (
                  <p className={styles.fieldError}>
                    {passwordFieldErrors.old_password}
                  </p>
                )}
              </label>

              <label className={styles.label}>
                New Password
                <div className={styles.passwordField}>
                  <input
                    className={`${styles.input} ${
                      passwordFieldErrors.new_password ? styles.inputError : ""
                    }`}
                    type={showPasswords.new ? "text" : "password"}
                    name="new_password"
                    value={passwordForm.new_password}
                    onChange={handlePasswordFormChange}
                    required
                    aria-invalid={Boolean(passwordFieldErrors.new_password)}
                  />
                  <button
                    type="button"
                    className={styles.toggleButton}
                    onClick={() =>
                      setShowPasswords((prev) => ({
                        ...prev,
                        new: !prev.new,
                      }))
                    }
                  >
                    {showPasswords.new ? "Hide" : "Show"}
                  </button>
                </div>
                {passwordFieldErrors.new_password && (
                  <p className={styles.fieldError}>
                    {passwordFieldErrors.new_password}
                  </p>
                )}
              </label>

              {/* Password Rules */}
              {passwordForm.new_password && (
                <div className={styles.passwordRules}>
                  <p>Password must contain:</p>
                  <ul>
                    <li className={passwordRules.hasMinLength ? styles.ruleMet : ""}>
                      {passwordRules.hasMinLength ? "✓" : "○"} At least 8 characters
                    </li>
                    <li className={passwordRules.hasUppercase ? styles.ruleMet : ""}>
                      {passwordRules.hasUppercase ? "✓" : "○"} One uppercase letter
                    </li>
                    <li className={passwordRules.hasLowercase ? styles.ruleMet : ""}>
                      {passwordRules.hasLowercase ? "✓" : "○"} One lowercase letter
                    </li>
                    <li className={passwordRules.hasDigit ? styles.ruleMet : ""}>
                      {passwordRules.hasDigit ? "✓" : "○"} One number
                    </li>
                    <li className={passwordRules.hasSpecial ? styles.ruleMet : ""}>
                      {passwordRules.hasSpecial ? "✓" : "○"} One special character
                    </li>
                  </ul>
                </div>
              )}

              <label className={styles.label}>
                Confirm New Password
                <div className={styles.passwordField}>
                  <input
                    className={`${styles.input} ${
                      passwordFieldErrors.confirm_password ? styles.inputError : ""
                    }`}
                    type={showPasswords.confirm ? "text" : "password"}
                    name="confirm_password"
                    value={passwordForm.confirm_password}
                    onChange={handlePasswordFormChange}
                    required
                    aria-invalid={Boolean(passwordFieldErrors.confirm_password)}
                  />
                  <button
                    type="button"
                    className={styles.toggleButton}
                    onClick={() =>
                      setShowPasswords((prev) => ({
                        ...prev,
                        confirm: !prev.confirm,
                      }))
                    }
                  >
                    {showPasswords.confirm ? "Hide" : "Show"}
                  </button>
                </div>
                {passwordFieldErrors.confirm_password && (
                  <p className={styles.fieldError}>
                    {passwordFieldErrors.confirm_password}
                  </p>
                )}
              </label>

              <div className={styles.buttonGroup}>
                <button
                  type="submit"
                  className={styles.primaryButton}
                  disabled={changePasswordLoading}
                >
                  {changePasswordLoading ? "Updating..." : "Update Password"}
                </button>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={() => {
                    setIsChangingPassword(false);
                    setPasswordForm({
                      old_password: "",
                      new_password: "",
                      confirm_password: "",
                    });
                    setPasswordFieldErrors({});
                    setPasswordFormError("");
                  }}
                  disabled={changePasswordLoading}
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
