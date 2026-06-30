"use client";

import { useCallback, useEffect, useState } from "react";
import {
  DIGEST_READING_SCALE_DEFAULT,
  DIGEST_READING_THEME_DEFAULT,
  loadDigestReadingComfort,
  nextDigestReadingScale,
  saveDigestReadingComfort,
  type DigestReadingComfortState,
  type DigestReadingTheme,
} from "@/lib/digest-reading-comfort";

export function useDigestReadingComfort() {
  const [state, setState] = useState<DigestReadingComfortState>({
    scale: DIGEST_READING_SCALE_DEFAULT,
    theme: DIGEST_READING_THEME_DEFAULT,
  });

  useEffect(() => {
    setState(loadDigestReadingComfort());
  }, []);

  const increaseScale = useCallback(() => {
    setState((current) => {
      const next = {
        ...current,
        scale: nextDigestReadingScale(current.scale, "increase"),
      };
      saveDigestReadingComfort(next);
      return next;
    });
  }, []);

  const decreaseScale = useCallback(() => {
    setState((current) => {
      const next = {
        ...current,
        scale: nextDigestReadingScale(current.scale, "decrease"),
      };
      saveDigestReadingComfort(next);
      return next;
    });
  }, []);

  const setTheme = useCallback((theme: DigestReadingTheme) => {
    setState((current) => {
      const next = { ...current, theme };
      saveDigestReadingComfort(next);
      return next;
    });
  }, []);

  return {
    scale: state.scale,
    theme: state.theme,
    increaseScale,
    decreaseScale,
    setTheme,
  };
}
