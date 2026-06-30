export type DigestReadingTheme = "light" | "paper" | "dark";

export const DIGEST_READING_SCALE_MIN = 0.85;
export const DIGEST_READING_SCALE_MAX = 1.5;
export const DIGEST_READING_SCALE_STEP = 0.1;
export const DIGEST_READING_SCALE_DEFAULT = 1;
export const DIGEST_READING_THEME_DEFAULT: DigestReadingTheme = "light";

const STORAGE_KEY = "ygip.digest-reading-comfort";

export interface DigestReadingComfortState {
  scale: number;
  theme: DigestReadingTheme;
}

function clampScale(value: number): number {
  const rounded =
    Math.round(value / DIGEST_READING_SCALE_STEP) * DIGEST_READING_SCALE_STEP;
  return Math.min(
    DIGEST_READING_SCALE_MAX,
    Math.max(DIGEST_READING_SCALE_MIN, Number(rounded.toFixed(2))),
  );
}

function isTheme(value: unknown): value is DigestReadingTheme {
  return value === "light" || value === "paper" || value === "dark";
}

export function loadDigestReadingComfort(): DigestReadingComfortState {
  if (typeof window === "undefined") {
    return {
      scale: DIGEST_READING_SCALE_DEFAULT,
      theme: DIGEST_READING_THEME_DEFAULT,
    };
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {
        scale: DIGEST_READING_SCALE_DEFAULT,
        theme: DIGEST_READING_THEME_DEFAULT,
      };
    }

    const parsed = JSON.parse(raw) as Partial<DigestReadingComfortState>;
    return {
      scale: clampScale(
        typeof parsed.scale === "number"
          ? parsed.scale
          : DIGEST_READING_SCALE_DEFAULT,
      ),
      theme: isTheme(parsed.theme)
        ? parsed.theme
        : DIGEST_READING_THEME_DEFAULT,
    };
  } catch {
    return {
      scale: DIGEST_READING_SCALE_DEFAULT,
      theme: DIGEST_READING_THEME_DEFAULT,
    };
  }
}

export function saveDigestReadingComfort(state: DigestReadingComfortState): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Tercih kaydı başarısız olursa okuma deneyimini kesmeyiz.
  }
}

export function nextDigestReadingScale(
  current: number,
  direction: "increase" | "decrease",
): number {
  const delta =
    direction === "increase"
      ? DIGEST_READING_SCALE_STEP
      : -DIGEST_READING_SCALE_STEP;
  return clampScale(current + delta);
}
