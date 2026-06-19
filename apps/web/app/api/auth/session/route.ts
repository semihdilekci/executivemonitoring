import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import type { UserMeResponse } from "@/types/api";
import {
  clearAuthCookies,
  getServerApiBaseUrl,
  setAuthCookies,
} from "@/lib/auth-cookies";
import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
} from "@/lib/constants";
import type { ApiErrorBody } from "@/types/api";

async function fetchMe(accessToken: string): Promise<Response> {
  return fetch(`${getServerApiBaseUrl()}/users/me`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });
}

export async function GET() {
  const cookieStore = await cookies();
  let accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;

  if (!accessToken) {
    const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
    if (!refreshToken) {
      return NextResponse.json({ user: null }, { status: 401 });
    }

    const refreshResponse = await fetch(`${getServerApiBaseUrl()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const refreshPayload = (await refreshResponse.json()) as
      | { access_token: string; expires_in: number }
      | ApiErrorBody;

    if (!refreshResponse.ok) {
      const response = NextResponse.json({ user: null }, { status: 401 });
      clearAuthCookies(response);
      return response;
    }

    accessToken = (refreshPayload as { access_token: string }).access_token;
    const expiresIn = (refreshPayload as { expires_in: number }).expires_in;

    const meResponse = await fetchMe(accessToken);
    if (!meResponse.ok) {
      const response = NextResponse.json({ user: null }, { status: 401 });
      clearAuthCookies(response);
      return response;
    }

    const user = (await meResponse.json()) as UserMeResponse;
    const response = NextResponse.json({
      user,
      access_token: accessToken,
      expires_in: expiresIn,
    });
    setAuthCookies(response, {
      access_token: accessToken,
      expires_in: expiresIn,
    });
    return response;
  }

  const meResponse = await fetchMe(accessToken);
  if (meResponse.ok) {
    const user = (await meResponse.json()) as UserMeResponse;
    return NextResponse.json({ user });
  }

  const refreshToken = cookieStore.get(REFRESH_TOKEN_COOKIE)?.value;
  if (!refreshToken) {
    const response = NextResponse.json({ user: null }, { status: 401 });
    clearAuthCookies(response);
    return response;
  }

  const refreshResponse = await fetch(`${getServerApiBaseUrl()}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  const refreshPayload = (await refreshResponse.json()) as
    | { access_token: string; expires_in: number }
    | ApiErrorBody;

  if (!refreshResponse.ok) {
    const response = NextResponse.json({ user: null }, { status: 401 });
    clearAuthCookies(response);
    return response;
  }

  const newAccessToken = (refreshPayload as { access_token: string }).access_token;
  const expiresIn = (refreshPayload as { expires_in: number }).expires_in;
  const retryMe = await fetchMe(newAccessToken);

  if (!retryMe.ok) {
    const response = NextResponse.json({ user: null }, { status: 401 });
    clearAuthCookies(response);
    return response;
  }

  const user = (await retryMe.json()) as UserMeResponse;
  const response = NextResponse.json({
    user,
    access_token: newAccessToken,
    expires_in: expiresIn,
  });
  setAuthCookies(response, {
    access_token: newAccessToken,
    expires_in: expiresIn,
  });
  return response;
}
