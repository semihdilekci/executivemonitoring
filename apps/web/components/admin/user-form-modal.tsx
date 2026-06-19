"use client";

import { useEffect, useState, type FormEvent } from "react";
import { PasswordPolicyIndicator } from "@/components/auth/password-policy-indicator";
import { FormErrorBanner } from "@/components/common/form-error-banner";
import { Modal } from "@/components/common/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { isPasswordPolicyValid } from "@/lib/password-policy";
import type { ApiError, UserListItem } from "@/types/api";
import type { UserRole } from "@/types/models";
import { isApiError } from "@/types/api";

type UserFormMode = "create" | "edit";

interface UserFormModalProps {
  mode: UserFormMode;
  user?: UserListItem;
  isOpen: boolean;
  isSubmitting?: boolean;
  isPasswordResetLoading?: boolean;
  onClose: () => void;
  onCreate: (values: {
    email: string;
    full_name: string;
    role: UserRole;
    password: string;
  }) => Promise<void>;
  onUpdate: (values: {
    full_name: string;
    role: UserRole;
  }) => Promise<void>;
  onPasswordReset?: () => Promise<void>;
}

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function getFormErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.code === "USER_EMAIL_EXISTS") {
      return "Bu e-posta adresi zaten kullanılıyor.";
    }
    if (error.code === "PASSWORD_POLICY_VIOLATION") {
      return error.message || "Şifre politikasına uymuyor.";
    }
    return error.message;
  }
  return "İşlem sırasında bir hata oluştu.";
}

export function UserFormModal({
  mode,
  user,
  isOpen,
  isSubmitting = false,
  isPasswordResetLoading = false,
  onClose,
  onCreate,
  onUpdate,
  onPasswordReset,
}: UserFormModalProps) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!isOpen) return;

    if (mode === "edit" && user) {
      setEmail(user.email);
      setFullName(user.full_name);
      setRole(user.role);
    } else {
      setEmail("");
      setFullName("");
      setRole("viewer");
    }
    setPassword("");
    setFormError(null);
    setFieldErrors({});
  }, [isOpen, mode, user]);

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (mode === "create") {
      if (!email.trim() || !isValidEmail(email.trim())) {
        errors.email = "Geçerli bir e-posta adresi girin.";
      }
      if (!password || !isPasswordPolicyValid(password)) {
        errors.password = "Şifre politikasına uymalıdır.";
      }
    }

    if (!fullName.trim() || fullName.trim().length < 2) {
      errors.full_name = "Ad soyad en az 2 karakter olmalı.";
    }

    if (!role) {
      errors.role = "Rol seçimi zorunludur.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);

    if (!validate() || isSubmitting) return;

    try {
      if (mode === "create") {
        await onCreate({
          email: email.trim(),
          full_name: fullName.trim(),
          role,
          password,
        });
      } else {
        await onUpdate({
          full_name: fullName.trim(),
          role,
        });
      }
    } catch (error) {
      setFormError(getFormErrorMessage(error as ApiError));
    }
  };

  const title = mode === "create" ? "Kullanıcı Oluştur" : "Kullanıcı Düzenle";
  const submitLabel = mode === "create" ? "Oluştur" : "Güncelle";

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4" noValidate>
        {formError ? <FormErrorBanner message={formError} /> : null}

        <Input
          label="E-posta"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          disabled={mode === "edit" || isSubmitting}
          error={fieldErrors.email}
          className={mode === "edit" ? "bg-gray-50" : undefined}
          onChange={(event) => setEmail(event.target.value)}
        />

        <Input
          label="Ad Soyad"
          name="full_name"
          type="text"
          autoComplete="name"
          value={fullName}
          disabled={isSubmitting}
          error={fieldErrors.full_name}
          onChange={(event) => setFullName(event.target.value)}
        />

        <div className="space-y-1.5">
          <label htmlFor="role" className="block text-sm font-medium text-gray-700">
            Rol
          </label>
          <select
            id="role"
            name="role"
            value={role}
            disabled={isSubmitting}
            onChange={(event) => setRole(event.target.value as UserRole)}
            className="flex h-10 w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="viewer">Viewer</option>
            <option value="admin">Admin</option>
          </select>
          {fieldErrors.role ? (
            <p className="text-sm text-red-500">{fieldErrors.role}</p>
          ) : null}
        </div>

        {mode === "create" ? (
          <div className="space-y-2">
            <Input
              label="Şifre"
              name="password"
              type="password"
              autoComplete="new-password"
              value={password}
              disabled={isSubmitting}
              error={fieldErrors.password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <PasswordPolicyIndicator password={password} />
          </div>
        ) : onPasswordReset ? (
          <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-3">
            <p className="text-sm text-gray-600">
              Şifre değişikliği için kullanıcıya sıfırlama bağlantısı gönderilir.
            </p>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="mt-3"
              disabled={isPasswordResetLoading || isSubmitting}
              onClick={() => void onPasswordReset()}
            >
              {isPasswordResetLoading
                ? "Gönderiliyor…"
                : "Şifre Sıfırlama Bağlantısı Gönder"}
            </Button>
          </div>
        ) : null}

        <div className="flex justify-end gap-3 pt-2">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isSubmitting}
          >
            İptal
          </Button>
          <Button type="submit" disabled={isSubmitting} aria-busy={isSubmitting}>
            {isSubmitting ? "Kaydediliyor…" : submitLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
