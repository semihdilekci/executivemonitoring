import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import type { LoginResponse } from "@/types/api";
import {
  getServerApiBaseUrl,
  setAuthCookies,
} from "@/lib/auth-cookies";
import type { ApiErrorBody } from "@/types/api";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as { email?: string; password?: string };

  const backendResponse = await fetch(`${getServerApiBaseUrl()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const payload = (await backendResponse.json()) as
    | LoginResponse
    | ApiErrorBody;

  if (!backendResponse.ok) {
    const response = NextResponse.json(payload, {
      status: backendResponse.status,
    });
    const retryAfter = backendResponse.headers.get("Retry-After");
    if (retryAfter) {
      response.headers.set("Retry-After", retryAfter);
    }
    return response;
  }

  const loginData = payload as LoginResponse;
  const response = NextResponse.json({
    user: loginData.user,
    access_token: loginData.access_token,
    expires_in: loginData.expires_in,
  });

  setAuthCookies(response, {
    access_token: loginData.access_token,
    refresh_token: loginData.refresh_token,
    expires_in: loginData.expires_in,
  });

  return response;
}
