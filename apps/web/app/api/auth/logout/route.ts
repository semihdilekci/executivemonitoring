import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { clearAuthCookies, getServerApiBaseUrl } from "@/lib/auth-cookies";
import { ACCESS_TOKEN_COOKIE } from "@/lib/constants";

export async function POST() {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_TOKEN_COOKIE)?.value;

  if (accessToken) {
    try {
      await fetch(`${getServerApiBaseUrl()}/auth/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
      });
    } catch {
      // Backend ulaşılamasa bile yerel oturum temizlenir
    }
  }

  const response = NextResponse.json({
    message: "Oturum sonlandırıldı.",
  });
  clearAuthCookies(response);
  return response;
}
