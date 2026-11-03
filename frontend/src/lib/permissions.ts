import type { User } from "../types";

export function hasPermission(user: User, permission: string): boolean {
  return user.role.permissions.some((item) => item.id === permission);
}
