"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  ReactNode,
  createElement,
} from "react";
import {
  apiFetch,
  API_BASE,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  ApiRequestError,
} from "@/lib/api";

export interface User {
  id: number;
  username: string;
  email: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
}

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface RegisterResponse {
  id: number;
  username: string;
  email: string;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<RegisterResponse>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Decode JWT payload to extract expiration and user data.
 * Does NOT verify the signature — that's the backend's job.
 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

function getTokenExpiry(token: string): number | null {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== "number") return null;
  return payload.exp * 1000; // Convert to milliseconds
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isAuthenticated = !!user;

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  const scheduleTokenRefresh = useCallback(
    (token: string) => {
      clearRefreshTimer();
      const expiry = getTokenExpiry(token);
      if (!expiry) return;

      // Refresh 60 seconds before expiry
      const refreshAt = expiry - Date.now() - 60_000;
      if (refreshAt <= 0) return;

      refreshTimerRef.current = setTimeout(async () => {
        const refreshTok = getRefreshToken();
        if (!refreshTok) return;

        try {
          const response = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshTok }),
          });

          if (response.ok) {
            const data: LoginResponse = await response.json();
            localStorage.setItem("access_token", data.access_token);
            if (data.refresh_token) {
              localStorage.setItem("refresh_token", data.refresh_token);
            }
            scheduleTokenRefresh(data.access_token);
          } else {
            clearTokens();
            setUser(null);
          }
        } catch {
          // Silent failure — next request will trigger refresh via apiFetch
        }
      }, refreshAt);
    },
    [clearRefreshTimer]
  );

  const login = useCallback(
    async (username: string, password: string): Promise<void> => {
      const data = await apiFetch<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);

      // Extract user info from token
      const payload = decodeJwtPayload(data.access_token);
      if (payload) {
        setUser({
          id: payload.sub as number,
          username: payload.username as string ?? username,
          email: payload.email as string ?? "",
        });
      }

      scheduleTokenRefresh(data.access_token);
    },
    [scheduleTokenRefresh]
  );

  const register = useCallback(
    async (username: string, email: string, password: string): Promise<RegisterResponse> => {
      const data = await apiFetch<RegisterResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, email, password }),
      });
      return data;
    },
    []
  );

  const logout = useCallback(async (): Promise<void> => {
    const refreshTok = getRefreshToken();
    clearRefreshTimer();

    try {
      if (refreshTok) {
        await apiFetch("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshTok }),
        });
      }
    } catch {
      // Silent — we clear local state regardless
    } finally {
      clearTokens();
      setUser(null);
    }
  }, [clearRefreshTimer]);

  const refreshToken = useCallback(async (): Promise<boolean> => {
    const refreshTok = getRefreshToken();
    if (!refreshTok) return false;

    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshTok }),
      });

      if (!response.ok) {
        clearTokens();
        setUser(null);
        return false;
      }

      const data: LoginResponse = await response.json();
      localStorage.setItem("access_token", data.access_token);
      if (data.refresh_token) {
        localStorage.setItem("refresh_token", data.refresh_token);
      }
      scheduleTokenRefresh(data.access_token);
      return true;
    } catch {
      clearTokens();
      setUser(null);
      return false;
    }
  }, [scheduleTokenRefresh]);

  // Initialize auth state from stored tokens on mount
  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      const payload = decodeJwtPayload(token);
      const expiry = getTokenExpiry(token);

      if (payload && expiry && expiry > Date.now()) {
        setUser({
          id: payload.sub as number,
          username: payload.username as string ?? "",
          email: payload.email as string ?? "",
        });
        scheduleTokenRefresh(token);
      } else {
        // Token expired — try refreshing
        refreshToken().finally(() => setIsLoading(false));
        return;
      }
    }
    setIsLoading(false);
  }, [scheduleTokenRefresh, refreshToken]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => clearRefreshTimer();
  }, [clearRefreshTimer]);

  const value: AuthContextValue = {
    isAuthenticated,
    user,
    isLoading,
    login,
    register,
    logout,
    refreshToken,
  };

  return createElement(AuthContext.Provider, { value }, children);
}

/**
 * Hook to access authentication state and actions.
 * Must be used within an AuthProvider.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export { ApiRequestError };
