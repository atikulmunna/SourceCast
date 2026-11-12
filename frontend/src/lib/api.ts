import axios, { AxiosError, AxiosRequestConfig, AxiosResponse } from "axios";
import { apiPath } from "./apiBase";

type SessionExpiredHandler = () => void;

let sessionExpiredHandler: SessionExpiredHandler | null = null;

export const api = axios.create({
  baseURL: apiPath("/api/v1"),
  withCredentials: true, // Required for HttpOnly refresh cookie
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

export function setSessionExpiredHandler(handler: SessionExpiredHandler | null) {
  sessionExpiredHandler = handler;
}

export function notifySessionExpired() {
  if (typeof window !== "undefined") {
    window.__sourcecast_access_token = undefined;
  }

  if (sessionExpiredHandler) {
    sessionExpiredHandler();
    return;
  }

  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

// One refresh at a time: concurrent callers share the in-flight request, because
// each refresh rotates the cookie and a second parallel refresh would be rejected.
let refreshInFlight: Promise<string> | null = null;

/**
 * Exchange the HttpOnly refresh cookie for a new access token.
 * Used by the axios interceptor and by fetch-based streams (chat), which the
 * interceptor cannot see. On failure the session is reported expired once.
 */
export function refreshAccessToken(): Promise<string> {
  if (!refreshInFlight) {
    refreshInFlight = api
      .post<{ access_token: string }>("/auth/refresh")
      .then(({ data }) => {
        if (typeof window !== "undefined") {
          window.__sourcecast_access_token = data.access_token;
        }
        return data.access_token;
      })
      .catch((error: unknown) => {
        notifySessionExpired();
        throw error;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

// ── Request interceptor: attach access token ──────────────────────────────────
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = window.__sourcecast_access_token;
    if (token && config.headers) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return config;
});

// ── Response interceptor: handle 401 → refresh → retry ────────────────────────
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & {
      _retry?: boolean;
    };

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/")
    ) {
      originalRequest._retry = true;
      // refreshAccessToken reports the expired session itself if it fails.
      const newToken = await refreshAccessToken();
      if (originalRequest.headers) {
        originalRequest.headers["Authorization"] = `Bearer ${newToken}`;
      }
      return api(originalRequest);
    }

    return Promise.reject(error);
  }
);

// Augment Window to hold access token in memory (not localStorage for XSS safety)
declare global {
  interface Window {
    __sourcecast_access_token?: string;
  }
}

export default api;
