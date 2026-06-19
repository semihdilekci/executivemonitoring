import { cn } from "@/lib/utils";
import {
  checkPasswordPolicy,
  type PasswordPolicyStatus,
} from "@/lib/password-policy";

interface PasswordPolicyIndicatorProps {
  password: string;
}

function PolicyRule({
  met,
  label,
}: {
  met: boolean;
  label: string;
}) {
  return (
    <li
      className={cn(
        "flex items-center gap-2 text-sm transition-colors",
        met ? "text-green-600" : "text-gray-500",
      )}
    >
      <span aria-hidden>{met ? "✓" : "○"}</span>
      <span>{label}</span>
    </li>
  );
}

export function PasswordPolicyIndicator({
  password,
}: PasswordPolicyIndicatorProps) {
  const status: PasswordPolicyStatus = checkPasswordPolicy(password);

  return (
    <ul className="space-y-1" aria-label="Şifre politikası gereksinimleri">
      <PolicyRule met={status.minLength} label="En az 8 karakter" />
      <PolicyRule met={status.hasUppercase} label="En az 1 büyük harf" />
      <PolicyRule met={status.hasDigit} label="En az 1 rakam" />
    </ul>
  );
}
