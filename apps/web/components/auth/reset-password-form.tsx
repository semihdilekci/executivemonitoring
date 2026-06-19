"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { completePasswordReset } from "@/lib/auth";
import type { ApiError } from "@/types/api";
import { getAuthErrorMessage } from "@/lib/auth-errors";
import {
  isPasswordPolicyValid,
} from "@/lib/password-policy";
import { AuthBrand } from "@/components/auth/auth-brand";
import { PasswordPolicyIndicator } from "@/components/auth/password-policy-indicator";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

interface ResetPasswordFormProps {
  token: string;
}

export function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isTokenInvalid, setIsTokenInvalid] = useState(false);

  useEffect(() => {
    if (!isSuccess) return;

    const timer = window.setTimeout(() => {
      router.replace("/login");
    }, 3000);

    return () => window.clearTimeout(timer);
  }, [isSuccess, router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setConfirmError(null);

    if (!isPasswordPolicyValid(password)) {
      setFormError(
        "Şifre en az 8 karakter, 1 büyük harf ve 1 rakam içermelidir.",
      );
      return;
    }

    if (password !== confirmPassword) {
      setConfirmError("Şifreler eşleşmiyor.");
      return;
    }

    setIsSubmitting(true);

    try {
      await completePasswordReset(token, password);
      setIsSuccess(true);
    } catch (error) {
      const apiError = error as ApiError;
      if (apiError.code === "AUTH_INVALID_RESET_TOKEN") {
        setIsTokenInvalid(true);
      } else {
        setFormError(getAuthErrorMessage(apiError));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isTokenInvalid) {
    return (
      <Card padding="lg" className="shadow-lg">
        <AuthBrand />
        <FormErrorBanner message="Bu şifre sıfırlama linki geçersiz veya süresi dolmuş. Yöneticinizden yeni bir link talep edin." />
        <div className="mt-6">
          <Link href="/login">
            <Button className="w-full" variant="secondary">
              Giriş Sayfasına Dön
            </Button>
          </Link>
        </div>
      </Card>
    );
  }

  if (isSuccess) {
    return (
      <Card padding="lg" className="shadow-lg">
        <AuthBrand />
        <div
          role="status"
          className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-center text-sm text-green-700"
        >
          Şifreniz güncellendi. Giriş sayfasına yönlendiriliyorsunuz…
        </div>
        <div className="mt-6">
          <Link href="/login">
            <Button className="w-full">Giriş Yap</Button>
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <Card padding="lg" className="shadow-lg">
      <AuthBrand />
      <h2 className="mb-6 text-center text-lg font-bold text-navy-800">
        Yeni Şifre Belirle
      </h2>

      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4" noValidate>
        {formError ? <FormErrorBanner message={formError} /> : null}

        <div className="space-y-1.5">
          <label htmlFor="new-password" className="block text-sm font-medium text-gray-700">
            Yeni şifre
          </label>
          <div className="relative">
            <input
              id="new-password"
              name="new-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              value={password}
              disabled={isSubmitting}
              onChange={(event) => setPassword(event.target.value)}
              className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 pr-10 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
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
        </div>

        <PasswordPolicyIndicator password={password} />

        <Input
          label="Şifre tekrar"
          name="confirm-password"
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          value={confirmPassword}
          disabled={isSubmitting}
          error={confirmError ?? undefined}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />

        <Button
          type="submit"
          className="w-full"
          disabled={isSubmitting}
          aria-busy={isSubmitting}
        >
          {isSubmitting ? "Güncelleniyor…" : "Şifreyi Güncelle"}
        </Button>
      </form>
    </Card>
  );
}
