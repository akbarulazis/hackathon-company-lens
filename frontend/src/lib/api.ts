/**
 * Authenticated fetch wrapper for the Company Lens API.
 * Automatically injects Authorization header and handles token refresh.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

interface ApiError {
  status: number;
  message: string;
  detail?: unknown;
}

export class ApiRequestError extends Error {
  status: number;
  detail?: unknown;

  constructor({ status, message, detail }: ApiError) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function setAccessToken(token: string): void {
  localStorage.setItem("access_token", token);
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

function clearTokens(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      clearTokens();
      return null;
    }

    const data = await response.json();
    setAccessToken(data.access_token);
    return data.access_token;
  } catch {
    clearTokens();
    return null;
  }
}

/**
 * Authenticated fetch wrapper.
 * Automatically attaches JWT access token and retries once on 401 with token refresh.
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;

  const makeRequest = async (token: string | null): Promise<Response> => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return fetch(url, {
      ...options,
      headers,
    });
  };

  let token = getAccessToken();
  let response = await makeRequest(token);

  // If 401, attempt token refresh and retry once
  if (response.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      response = await makeRequest(newToken);
    } else {
      // Redirect to login if refresh fails
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new ApiRequestError({
        status: 401,
        message: "Session expired. Please log in again.",
      });
    }
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new ApiRequestError({
      status: response.status,
      message: errorBody.detail ?? response.statusText,
      detail: errorBody,
    });
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// Typed request helpers
export function get<T = unknown>(path: string, options?: RequestInit): Promise<T> {
  return apiFetch<T>(path, { ...options, method: "GET" });
}

export function post<T = unknown>(path: string, body?: unknown, options?: RequestInit): Promise<T> {
  return apiFetch<T>(path, {
    ...options,
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function put<T = unknown>(path: string, body?: unknown, options?: RequestInit): Promise<T> {
  return apiFetch<T>(path, {
    ...options,
    method: "PUT",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function del<T = unknown>(path: string, options?: RequestInit): Promise<T> {
  return apiFetch<T>(path, { ...options, method: "DELETE" });
}

export { getAccessToken, setAccessToken, getRefreshToken, clearTokens, API_BASE };
