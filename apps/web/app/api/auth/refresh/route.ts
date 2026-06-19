import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import type { RefreshResponse } from "@/types/api";
import {
  clearAuthCookies,
  getServerApiBaseUrl,
  setAuthCookies,
} from "@/lib/auth-cookies";
import { REFRESH_TOKEN_COOKIE } from "@/lib/constants";
import type { ApiErrorBody } from "@/types/api";

export async function POST() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;

  if (!refreshToken) {
    return NextResponse.json(
      {
        error: {
          code: "AUTH_INVALID_REFRESH_TOKEN",
          message: "Oturum süresi doldu. Lütfen yeniden giriş yapın.",
          details: {},
        },
      },
      { status: 401 },
    );
  }

  const backendResponse = await fetch(`${getServerApiBaseUrl()}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  const payload = (await backendResponse.json()) as
    | RefreshResponse
    | ApiErrorBody;

  if (!backendResponse.ok) {
    const response = NextResponse.json(payload, {
      status: backendResponse.status,
    });
    clearAuthCookies(response);
    return response;
  }

  const refreshData = payload as RefreshResponse;
  const response = NextResponse.json({
    access_token: refreshData.access_token,
    expires_in: refreshData.expires_in,
  });

  setAuthCookies(response, {
    access_token: refreshData.access_token,
    expires_in: refreshData.expires_in,
  });

  return response;
}
