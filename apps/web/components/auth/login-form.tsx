"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";
import type { ApiError } from "@/types/api";
import {
  getAuthErrorMessage,
  getRetryAfterSeconds,
} from "@/lib/auth-errors";
import { APP_ENV } from "@/lib/constants";
import { AuthBrand } from "@/components/auth/auth-brand";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export function LoginForm() {
  const formRef = useRef<HTMLFormElement>(null);
  const searchParams = useSearchParams();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLockOn, setCapsLockOn] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{
    email?: string;
    password?: string;
  }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [retryAfter, setRetryAfter] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (retryAfter === null || retryAfter <= 0) return;

    const timer = window.setInterval(() => {
      setRetryAfter((current) => {
        if (current === null || current <= 1) {
          window.clearInterval(timer);
          return null;
        }
        return current - 1;
      });
    }, 1000);

    return () => window.clearInterval(timer);
  }, [retryAfter]);

  const resolveCredentials = () => {
    const form = formRef.current;
    if (!form) {
      return { email: email.trim(), password };
    }

    const formData = new FormData(form);
    return {
      email: String(formData.get("email") ?? "").trim(),
      password: String(formData.get("password") ?? ""),
    };
  };

  const validate = (
    emailValue: string,
    passwordValue: string,
  ): boolean => {
    const errors: { email?: string; password?: string } = {};

    if (!emailValue) {
      errors.email = "Geçerli bir e-posta adresi girin.";
    } else if (!isValidEmail(emailValue)) {
      errors.email = "Geçerli bir e-posta adresi girin.";
    }

    if (!passwordValue) {
      errors.password = "Şifre alanı boş bırakılamaz.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async () => {
    const credentials = resolveCredentials();

    setFormError(null);
    setEmail(credentials.email);
    setPassword(credentials.password);

    if (retryAfter !== null) {
      return;
    }

    if (!validate(credentials.email, credentials.password)) {
      setFormError("Lütfen e-posta ve şifrenizi kontrol edin.");
      return;
    }

    setIsSubmitting(true);

    try {
      await login(credentials.email, credentials.password);
      const redirectTo = searchParams.get("from") || "/";
      window.location.assign(redirectTo);
      return;
    } catch (error) {
      const apiError = error as ApiError;
      const retrySeconds = getRetryAfterSeconds(apiError);

      if (retrySeconds !== null) {
        setRetryAfter(retrySeconds);
        setFormError(`Çok fazla deneme. Lütfen ${retrySeconds} saniye bekleyin.`);
      } else {
        setFormError(getAuthErrorMessage(apiError));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const isDisabled = isSubmitting || retryAfter !== null;

  return (
    <Card padding="lg" className="shadow-lg">
      <AuthBrand />

      <form
        ref={formRef}
        onSubmit={(event) => {
          event.preventDefault();
          void handleSubmit();
        }}
        className="space-y-4"
        noValidate
      >
        {formError ? (
          <FormErrorBanner
            message={
              retryAfter !== null
                ? `Çok fazla deneme. Lütfen ${retryAfter} saniye bekleyin.`
                : formError
            }
          />
        ) : null}

        <Input
          label="E-posta"
          name="email"
          type="email"
          autoComplete="email"
          autoFocus
          value={email}
          disabled={isDisabled}
          error={fieldErrors.email}
          onChange={(event) => setEmail(event.target.value)}
        />

        <div className="space-y-1.5">
          <label htmlFor="password" className="block text-sm font-medium text-gray-700">
            Şifre
          </label>
          <div className="relative">
            <input
              id="password"
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              disabled={isDisabled}
              onChange={(event) => setPassword(event.target.value)}
              onKeyDown={(event) => {
                setCapsLockOn(event.getModifierState("CapsLock"));
              }}
              onKeyUp={(event) => {
                setCapsLockOn(event.getModifierState("CapsLock"));
              }}
              className={cn(
                "flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 pr-10 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50",
                fieldErrors.password && "border-red-400 focus-visible:ring-red-400",
              )}
            />
            <button
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-1 text-xs font-medium text-gray-500 hover:text-navy-800"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? "Şifreyi gizle" : "Şifreyi göster"}
              tabIndex={-1}
            >
              {showPassword ? "Gizle" : "Göster"}
            </button>
          </div>
          {fieldErrors.password ? (
            <p className="text-sm text-red-500">{fieldErrors.password}</p>
          ) : null}
          {capsLockOn ? (
            <p className="text-xs text-amber-600" role="status">
              Caps Lock açık
            </p>
          ) : null}
        </div>

        <Button
          type="submit"
          className="w-full"
          disabled={isDisabled}
          aria-busy={isSubmitting}
        >
          {isSubmitting ? "Giriş yapılıyor…" : "Giriş Yap"}
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-gray-500">
        Şifre sıfırlama talebiniz için yöneticinize başvurun.
      </p>

      {APP_ENV === "development" ? (
        <p className="mt-3 text-center text-xs text-gray-400">
          Geliştirme: admin@ygip.test / DevPass1
        </p>
      ) : null}
    </Card>
  );
}
