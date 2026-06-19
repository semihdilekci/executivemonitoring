import axios from "axios";
import type { User } from "@/types/models";
import type {
  ApiError,
  ApiErrorBody,
  LoginResponse,
  UserMeResponse,
} from "@/types/api";
import { apiClient, normalizeError } from "./api-client";
import { tokenStore } from "./token-store";

const authProxyClient = axios.create({
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

function mapUser(response: UserMeResponse | LoginResponse["user"]): User {
  return {
    id: response.id,
    email: response.email,
    fullName: response.full_name,
    role: response.role,
  };
}

function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    if (error.response?.data) {
      const data = error.response.data as ApiErrorBody;
      if (data.error) {
        const apiError: ApiError = {
          code: data.error.code,
          message: data.error.message,
          details: data.error.details ?? {},
          statusCode: error.response.status,
        };
        const retryAfter = error.response.headers?.["retry-after"];
        if (retryAfter) {
          const parsed = Number.parseInt(String(retryAfter), 10);
          if (!Number.isNaN(parsed)) {
            apiError.details.retry_after_seconds = parsed;
          }
        }
        return apiError;
      }
    }
    return normalizeError(error);
  }

  return {
    code: "NETWORK_ERROR",
    message: "Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.",
    details: {},
    statusCode: 0,
  };
}

export async function login(email: string, password: string): Promise<User> {
  try {
    const { data } = await authProxyClient.post<{
      user: LoginResponse["user"];
      access_token: string;
    }>("/api/auth/login", { email, password });

    tokenStore.setAccessToken(data.access_token);
    return mapUser(data.user);
  } catch (error) {
    throw toApiError(error);
  }
}

export async function logout(): Promise<void> {
  try {
    await authProxyClient.post("/api/auth/logout");
  } finally {
    tokenStore.clearTokens();
  }
}

export async function fetchCurrentUser(): Promise<User | null> {
  try {
    const { data } = await authProxyClient.get<{
      user: UserMeResponse;
      access_token?: string;
    }>("/api/auth/session");

    if (data.access_token) {
      tokenStore.setAccessToken(data.access_token);
    }

    return mapUser(data.user);
  } catch {
    tokenStore.clearTokens();
    return null;
  }
}

export async function completePasswordReset(
  token: string,
  newPassword: string,
): Promise<void> {
  try {
    await apiClient.post("/auth/password-reset/complete", {
      token,
      new_password: newPassword,
    });
  } catch (error) {
    throw toApiError(error);
  }
}

export { tokenStore };
