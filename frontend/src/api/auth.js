/**
 * Authentication API calls.
 * Maps to FastAPI routes under /api/auth/
 */

import apiClient from "./client";

export const authApi = {
  /**
   * POST /api/auth/register
   * @param {{ username, email, password, full_name? }} data
   */
  register(data) {
    return apiClient.post("/api/auth/register", data);
  },

  /**
   * POST /api/auth/login
   * @param {{ username, password }} data
   * @returns {{ access_token, user_id, username, role, expires_in }}
   */
  login(data) {
    return apiClient.post("/api/auth/login", data);
  },

  /**
   * POST /api/auth/refresh  (requires Bearer token)
   */
  refresh() {
    return apiClient.post("/api/auth/refresh");
  },

  /**
   * GET /api/auth/me  (requires Bearer token)
   */
  me() {
    return apiClient.get("/api/auth/me");
  },

  /**
   * GET /api/auth/me  (requires Bearer token)
   * Alias for me() with clearer naming
   */
  getMe() {
    return apiClient.get("/api/auth/me");
  },

  /**
   * PUT /api/auth/me  (requires Bearer token)
   * @param {string} fullName - User's full name
   */
  updateMe(fullName) {
    return apiClient.put("/api/auth/me", null, {
      params: { full_name: fullName },
    });
  },

  /**
   * POST /api/auth/reset-password  (requires Bearer token)
   * @param {string} oldPassword - Current password
   * @param {string} newPassword - New password
   */
  resetPassword(oldPassword, newPassword) {
    return apiClient.post("/api/auth/reset-password", null, {
      params: {
        old_password: oldPassword,
        new_password: newPassword,
      },
    });
  },
};
