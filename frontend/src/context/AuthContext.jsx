/**
 * AuthContext — global authentication state.
 *
 * Provides:
 *   user         — { user_id, username, role } or null when logged out
 *   token        — JWT string or null
 *   login(data)  — persists token + user info after successful /login call
 *   logout()     — clears all stored credentials
 *   isAdmin      — convenience boolean
 */

import { createContext, useContext, useState, useCallback } from "react";

const AuthContext = createContext(null);

function loadStoredAuth() {
  try {
    const token = localStorage.getItem("ttc_token");
    const user = JSON.parse(localStorage.getItem("ttc_user") || "null");
    return { token, user };
  } catch {
    return { token: null, user: null };
  }
}

export function AuthProvider({ children }) {
  const stored = loadStoredAuth();
  const [token, setToken] = useState(stored.token);
  const [user, setUser] = useState(stored.user);

  const login = useCallback((tokenResponse) => {
    const { access_token, user_id, username, role } = tokenResponse;
    const userInfo = { user_id, username, role };
    localStorage.setItem("ttc_token", access_token);
    localStorage.setItem("ttc_user", JSON.stringify(userInfo));
    setToken(access_token);
    setUser(userInfo);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("ttc_token");
    localStorage.removeItem("ttc_user");
    setToken(null);
    setUser(null);
  }, []);

  const isAdmin = user?.role === "admin";

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
