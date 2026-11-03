import type { ApiErrorPayload, BusinessSettings, User } from "../types";

const API_ROOT = "/api/v1";

export class ApiError extends Error {
  readonly status: number;

  constructor(
    message: string,
    status: number,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function readCsrfToken(cookieString: string): string | null {
  const csrfCookie = cookieString
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith("mjd_csrf="));

  if (!csrfCookie) return null;
  return decodeURIComponent(csrfCookie.slice("mjd_csrf=".length));
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && path !== "/auth/login") {
    const csrfToken = readCsrfToken(document.cookie);
    if (!csrfToken) throw new ApiError("Your session expired. Please sign in again.", 403);
    headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(`${API_ROOT}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const body = await response.text();
    let payload: ApiErrorPayload = {};
    try {
      payload = JSON.parse(body) as ApiErrorPayload;
    } catch {
      // Reverse proxies can return plain-text errors when the API is unavailable.
    }
    const message = payload.detail
      ?? (response.status >= 500
        ? `The API server returned HTTP ${response.status}. Check that the backend and database are running.`
        : "Something went wrong. Please try again.");
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  async currentUser(): Promise<User | null> {
    try {
      return await request<User>("/auth/me");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null;
      throw error;
    }
  },

  login(email: string, password: string): Promise<User> {
    return request<User>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  logout(): Promise<void> {
    return request<void>("/auth/logout", { method: "POST" });
  },

  changePassword(current_password: string, new_password: string): Promise<void> {
    return request<void>("/auth/password", {
      method: "PUT",
      body: JSON.stringify({ current_password, new_password }),
    });
  },

  getSettings(): Promise<BusinessSettings> {
    return request<BusinessSettings>("/settings");
  },

  updateSettings(settings: BusinessSettings): Promise<BusinessSettings> {
    return request<BusinessSettings>("/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
  },
};
