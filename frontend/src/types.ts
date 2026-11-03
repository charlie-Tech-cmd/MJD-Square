export interface Permission {
  id: string;
  description: string;
}

export interface Role {
  id: string;
  name: string;
  permissions: Permission[];
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
}

export interface BusinessSettings {
  business_name: string;
  currency: string;
  timezone: string;
  payment_methods: string[];
}

export interface RolePermissionOption {
  id: string;
  description: string;
  granted: boolean;
}

export interface RolePermissions {
  role_id: string;
  role_name: string;
  permissions: RolePermissionOption[];
}

export interface ApiErrorPayload {
  detail?: string;
}
