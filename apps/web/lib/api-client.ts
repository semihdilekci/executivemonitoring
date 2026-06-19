import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";
import type { ApiError, ApiErrorBody } from "@/types/api";
import { API_BASE_URL } from "./constants";
import { tokenStore } from "./token-store";

interface RetryableRequest extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

let refreshPromise: Promise<string> | null = null;

const authProxyClient = axios.create({
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

export function normalizeError(error: AxiosError): ApiError {
  const data = error.response?.data as ApiErrorBody | undefined;
  if (data?.error) {
    return {
      code: data.error.code,
      message: data.error.message,
      details: data.error.details ?? {},
      statusCode: error.response?.status ?? 0,
    };
  }

  return {
    code: "NETWORK_ERROR",
    message: "Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.",
    details: {},
    statusCode: error.response?.status ?? 0,
  };
}

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    const response = await authProxyClient.post<{
      access_token: string;
    }>("/api/auth/refresh");

    const newToken = response.data.access_token;
    tokenStore.setAccessToken(newToken);
    return newToken;
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

function redirectToLogin(): void {
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30_000,
    headers: { "Content-Type": "application/json" },
    withCredentials: true,
  });

  client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = tokenStore.getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as RetryableRequest | undefined;

      if (
        error.response?.status === 401 &&
        originalRequest &&
        !originalRequest._retry &&
        !originalRequest.url?.includes("/auth/login") &&
        !originalRequest.url?.includes("/auth/refresh") &&
        !originalRequest.url?.includes("/auth/password-reset")
      ) {
        originalRequest._retry = true;

        try {
          const newToken = await refreshAccessToken();
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return client(originalRequest);
        } catch {
          tokenStore.clearTokens();
          redirectToLogin();
        }
      }

      return Promise.reject(normalizeError(error));
    },
  );

  return client;
}

export const apiClient = createApiClient();
