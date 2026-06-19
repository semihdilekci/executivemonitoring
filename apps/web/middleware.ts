import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  ACCESS_TOKEN_COOKIE,
  ADMIN_PATH_PREFIX,
  API_BASE_URL,
  PUBLIC_PATHS,
} from "./lib/constants";

function decodeTokenRole(token: string | undefined): string | null {
  if (!token) return null;

  try {
    const payloadSegment = token.split(".")[1];
    if (!payloadSegment) return null;

    const normalized = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - (normalized.length % 4)) % 4),
      "=",
    );
    const payload = JSON.parse(atob(padded)) as { role?: string };
    return payload.role ?? null;
  } catch {
    return null;
  }
}

function buildCspHeader(): string {
  let apiOrigin = "'self'";
  try {
    apiOrigin = new URL(API_BASE_URL).origin;
  } catch {
    // Varsayılan 'self' kalır
  }

  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https:",
    "font-src 'self'",
    `connect-src 'self' ${apiOrigin}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
}

function applySecurityHeaders(response: NextResponse): NextResponse {
  response.headers.set("Content-Security-Policy", buildCspHeader());
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set(
    "Strict-Transport-Security",
    "max-age=31536000; includeSubDomains",
  );
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  return response;
}

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((path) => pathname.startsWith(path));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/api/auth")) {
    return applySecurityHeaders(NextResponse.next());
  }

  const token = request.cookies.get(ACCESS_TOKEN_COOKIE)?.value;

  if (isPublicPath(pathname) && token) {
    return applySecurityHeaders(
      NextResponse.redirect(new URL("/", request.url)),
    );
  }

  if (!isPublicPath(pathname) && !token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return applySecurityHeaders(NextResponse.redirect(loginUrl));
  }

  if (pathname.startsWith(ADMIN_PATH_PREFIX)) {
    const role = decodeTokenRole(token);
    if (role !== "admin") {
      return applySecurityHeaders(
        NextResponse.redirect(new URL("/", request.url)),
      );
    }
  }

  return applySecurityHeaders(NextResponse.next());
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
