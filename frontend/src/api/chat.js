/**
 * Chat / session API calls.
 * Maps to FastAPI routes under /api/ and the /chat endpoint in main.py.
 */

import apiClient from "./client";

export const chatApi = {
  /**
   * POST /chat
   * Send a user message and receive the bot response.
   * @param {{ message: string, session_id?: string }} data
   */
  sendMessage(data) {
    return apiClient.post("/chat", data);
  },

  /**
   * POST /api/sessions
   * Create a new conversation session.
   * @param {{ topic?: string }} data
   */
  createSession(data = {}) {
    return apiClient.post("/api/sessions", data);
  },

  /**
   * GET /api/sessions/:id
   */
  getSession(sessionId) {
    return apiClient.get(`/api/sessions/${sessionId}`);
  },

  /**
   * GET /api/sessions
   * List sessions for the current user.
   * @param {{ limit?: number }} params
   */
  listSessions(params = {}) {
    return apiClient.get("/api/sessions", { params });
  },

  /**
   * PATCH /api/sessions/:id
   * Update session topic.
   */
  updateSession(sessionId, data) {
    return apiClient.patch(`/api/sessions/${sessionId}`, data);
  },

  /**
   * POST /api/sessions/:id/feedback
   * @param {{ feedback_score: number }} data
   */
  submitFeedback(sessionId, data) {
    return apiClient.post(`/api/sessions/${sessionId}/feedback`, data);
  },

  /**
   * GET /api/sessions/:id/messages
   */
  getMessages(sessionId) {
    return apiClient.get(`/api/sessions/${sessionId}/messages`);
  },
};
