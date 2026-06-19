export interface PasswordPolicyStatus {
  minLength: boolean;
  hasUppercase: boolean;
  hasDigit: boolean;
}

export function checkPasswordPolicy(password: string): PasswordPolicyStatus {
  return {
    minLength: password.length >= 8,
    hasUppercase: /[A-Z]/.test(password),
    hasDigit: /\d/.test(password),
  };
}

export function isPasswordPolicyValid(password: string): boolean {
  const status = checkPasswordPolicy(password);
  return status.minLength && status.hasUppercase && status.hasDigit;
}
