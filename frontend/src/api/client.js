/**
 * Axios client configured to talk to the TTC chatbot FastAPI backend.
 * Base URL reads from VITE_API_URL env variable, defaults to localhost:8000.
 */

import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token to every request if present
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("ttc_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401 clear stored credentials and redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const hadToken = Boolean(localStorage.getItem("ttc_token"));

    // Only force sign-out redirect when an authenticated session exists.
    // This prevents login/register 401 responses from causing a page reload.
    if (error.response?.status === 401 && hadToken) {
      localStorage.removeItem("ttc_token");
      localStorage.removeItem("ttc_user");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default apiClient;
