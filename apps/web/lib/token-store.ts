/** In-memory token store — access/refresh JS memory'de; httpOnly cookie İterasyon 6.2'de. */

interface TokenStore {
  getAccessToken(): string | null;
  setAccessToken(token: string): void;
  getRefreshToken(): string | null;
  setRefreshToken(token: string): void;
  clearTokens(): void;
}

function createTokenStore(): TokenStore {
  let accessToken: string | null = null;
  let refreshToken: string | null = null;

  return {
    getAccessToken: () => accessToken,
    setAccessToken: (token: string) => {
      accessToken = token;
    },
    getRefreshToken: () => refreshToken,
    setRefreshToken: (token: string) => {
      refreshToken = token;
    },
    clearTokens: () => {
      accessToken = null;
      refreshToken = null;
    },
  };
}

export const tokenStore = createTokenStore();
