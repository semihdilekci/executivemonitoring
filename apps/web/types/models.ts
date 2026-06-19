export type UserRole = "admin" | "viewer";

export interface User {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
}

export interface NavItem {
  label: string;
  href: string;
}
