import type { NextResponse } from "next/server";
import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  REFRESH_TOKEN_MAX_AGE_SECONDS,
} from "./constants";

const isProduction = process.env.NODE_ENV === "production";

interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
}

function baseCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: isProduction,
    sameSite: "strict" as const,
    path: "/",
    maxAge,
  };
}

export function setAuthCookies(
  response: NextResponse,
  tokens: AuthTokens,
): void {
  response.cookies.set(
    ACCESS_TOKEN_COOKIE,
    tokens.access_token,
    baseCookieOptions(tokens.expires_in),
  );

  if (tokens.refresh_token) {
    response.cookies.set(
      REFRESH_TOKEN_COOKIE,
      tokens.refresh_token,
      baseCookieOptions(REFRESH_TOKEN_MAX_AGE_SECONDS),
    );
  }
}

export function clearAuthCookies(response: NextResponse): void {
  response.cookies.set(ACCESS_TOKEN_COOKIE, "", {
    ...baseCookieOptions(0),
    maxAge: 0,
  });
  response.cookies.set(REFRESH_TOKEN_COOKIE, "", {
    ...baseCookieOptions(0),
    maxAge: 0,
  });
}

export function getServerApiBaseUrl(): string {
  // Next route handler'ları (login/refresh/logout/session) backend'e SERVER-side
  // gider; bu yüzden her zaman absolute bir URL gerekir. ngrok tek-tünel
  // demosunda NEXT_PUBLIC_API_BASE_URL relative ("/api/v1") yapılır, o durumda
  // API_INTERNAL_BASE_URL devreye girer. Normal local dev'de ikisi de boşsa
  // localhost'a düşer.
  return (
    process.env.API_INTERNAL_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000/api/v1"
  );
}
