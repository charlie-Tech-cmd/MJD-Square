import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, UserPlus, Users, UserX } from "lucide-react";
import { useState } from "react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, readCsrfToken } from "../lib/api";
import type { RolePermissions } from "../types";

interface StaffAccount {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
  role: { id: string; name: string };
}

const staffFormSchema = z.object({
  full_name: z.string().trim().min(1, "Enter the staff member's name."),
  email: z.email("Enter a valid email address."),
  password: z.string().min(12, "Use at least 12 characters.").max(128),
});

type StaffFormValues = z.infer<typeof staffFormSchema>;

async function fetchStaff(): Promise<StaffAccount[]> {
  const response = await fetch("/api/v1/users", { credentials: "include" });
  if (!response.ok) {
    const body = (await response.json()) as { detail?: string };
    throw new ApiError(body.detail ?? "Unable to load staff accounts.", response.status);
  }
  return response.json() as Promise<StaffAccount[]>;
}

async function createStaff(values: StaffFormValues): Promise<StaffAccount> {
  const csrf = readCsrfToken(document.cookie);
  if (!csrf) throw new ApiError("Your session expired. Please sign in again.", 403);
  const response = await fetch("/api/v1/users", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify(values),
  });
  if (!response.ok) {
    const body = (await response.json()) as { detail?: string };
    throw new ApiError(body.detail ?? "Unable to create staff account.", response.status);
  }
  return response.json() as Promise<StaffAccount>;
}

async function deactivateStaff(id: string): Promise<void> {
  const csrf = readCsrfToken(document.cookie);
  if (!csrf) throw new ApiError("Your session expired. Please sign in again.", 403);
  const response = await fetch(`/api/v1/users/${id}`, {
    method: "DELETE",
    credentials: "include",
    headers: { "X-CSRF-Token": csrf },
  });
  if (!response.ok) {
    const body = (await response.json()) as { detail?: string };
    throw new ApiError(body.detail ?? "Unable to deactivate staff account.", response.status);
  }
}

async function fetchStaffPermissions(): Promise<RolePermissions> {
  const response = await fetch("/api/v1/roles/staff/permissions", { credentials: "include" });
  if (!response.ok) {
    const body = (await response.json()) as { detail?: string };
    throw new ApiError(body.detail ?? "Unable to load staff permissions.", response.status);
  }
  return response.json() as Promise<RolePermissions>;
}

async function updateStaffPermissions(permission_ids: string[]): Promise<RolePermissions> {
  const csrf = readCsrfToken(document.cookie);
  if (!csrf) throw new ApiError("Your session expired. Please sign in again.", 403);
  const response = await fetch("/api/v1/roles/staff/permissions", {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify({ permission_ids }),
  });
  if (!response.ok) {
    const body = (await response.json()) as { detail?: string };
    throw new ApiError(body.detail ?? "Unable to update staff permissions.", response.status);
  }
  return response.json() as Promise<RolePermissions>;
}

export function TeamPage() {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [permissionError, setPermissionError] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const staffQuery = useQuery({ queryKey: ["staff"], queryFn: fetchStaff });
  const staffPermissionsQuery = useQuery({
    queryKey: ["staff-permissions"],
    queryFn: fetchStaffPermissions,
  });
  const form = useForm<StaffFormValues>({ resolver: zodResolver(staffFormSchema) });
  useEffect(() => {
    if (staffPermissionsQuery.data) {
      setSelectedPermissions(
        staffPermissionsQuery.data.permissions
          .filter((permission) => permission.granted)
          .map((permission) => permission.id),
      );
    }
  }, [staffPermissionsQuery.data]);
  const createMutation = useMutation({
    mutationFn: createStaff,
    onSuccess: async () => {
      setActionError("");
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ["staff"] });
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to create staff account."),
  });
  const deactivateMutation = useMutation({
    mutationFn: deactivateStaff,
    onSuccess: async () => {
      setActionError("");
      await queryClient.invalidateQueries({ queryKey: ["staff"] });
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to deactivate staff account."),
  });
  const permissionsMutation = useMutation({
    mutationFn: updateStaffPermissions,
    onSuccess: async (permissions) => {
      setPermissionError("");
      setSelectedPermissions(
        permissions.permissions
          .filter((permission) => permission.granted)
          .map((permission) => permission.id),
      );
      await queryClient.invalidateQueries({ queryKey: ["staff-permissions"] });
    },
    onError: (error) =>
      setPermissionError(
        error instanceof ApiError ? error.message : "Unable to update staff permissions.",
      ),
  });

  const submit = form.handleSubmit((values) => createMutation.mutate(values));

  return (
    <div className="settings-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">ACCESS CONTROL</span>
          <h1>Staff and permissions</h1>
          <p>Manage staff access. Every authorization is checked by the API.</p>
        </div>
      </div>
      <div className="team-layout">
        <form className="settings-card team-create-card" onSubmit={submit}>
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><UserPlus size={18} /></span>
            <div><h2>Add shop staff</h2><p>New accounts receive the limited shop-staff role.</p></div>
          </div>
          <div className="settings-fields team-form-fields">
            <label className="field">
              <span>Full name</span>
              <input {...form.register("full_name")} aria-invalid={Boolean(form.formState.errors.full_name)} />
              {form.formState.errors.full_name && <small className="field-error">{form.formState.errors.full_name.message}</small>}
            </label>
            <label className="field">
              <span>Email address</span>
              <input autoComplete="off" type="email" {...form.register("email")} aria-invalid={Boolean(form.formState.errors.email)} />
              {form.formState.errors.email && <small className="field-error">{form.formState.errors.email.message}</small>}
            </label>
            <label className="field">
              <span>Temporary password</span>
              <input autoComplete="new-password" type="password" {...form.register("password")} aria-invalid={Boolean(form.formState.errors.password)} />
              <small className="field-help">Share it securely and have the staff member change it after signing in.</small>
              {form.formState.errors.password && <small className="field-error">{form.formState.errors.password.message}</small>}
            </label>
          </div>
          {actionError && <p className="form-alert" role="alert">{actionError}</p>}
          <div className="settings-card-footer">
            <span className="settings-hint">Staff cannot access owner-only settings.</span>
            <button className="button button-primary" disabled={createMutation.isPending} type="submit">
              {createMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <UserPlus size={16} />}
              Create account
            </button>
          </div>
        </form>

        <section className="settings-card team-list-card">
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><Users size={18} /></span>
            <div><h2>Team accounts</h2><p>Deactivated accounts lose access immediately.</p></div>
          </div>
          {staffQuery.isPending ? (
            <div className="loading-panel"><LoaderCircle className="spin" size={19} /> Loading staff…</div>
          ) : staffQuery.isError ? (
            <p className="form-alert" role="alert">
              {staffQuery.error instanceof ApiError ? staffQuery.error.message : "Unable to load staff."}
            </p>
          ) : (
            <div className="staff-list">
              {staffQuery.data.map((staff) => (
                <article className="staff-row" key={staff.id}>
                  <span className="profile-avatar">{staff.full_name.slice(0, 1).toUpperCase()}</span>
                  <div className="staff-details">
                    <strong>{staff.full_name}</strong>
                    <small>{staff.email} · {staff.role.name}</small>
                  </div>
                  <span className={`staff-status${staff.is_active ? " staff-status-active" : ""}`}>
                    {staff.is_active ? "Active" : "Inactive"}
                  </span>
                  {staff.is_active && staff.role.name === "Shop staff" && (
                    <button
                      aria-label={`Deactivate ${staff.full_name}`}
                      className="icon-button staff-deactivate"
                      disabled={deactivateMutation.isPending}
                      onClick={() => {
                        if (window.confirm(`Deactivate ${staff.full_name}'s account?`)) {
                          deactivateMutation.mutate(staff.id);
                        }
                      }}
                      title="Deactivate account"
                      type="button"
                    >
                      <UserX size={16} />
                    </button>
                  )}
                </article>
              ))}
              {staffQuery.data.length === 0 && <p className="empty-staff">No team accounts yet.</p>}
            </div>
          )}
        </section>
        <section className="settings-card team-permissions-card">
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><Users size={18} /></span>
            <div>
              <h2>Shop staff access</h2>
              <p>Changes apply to every account with the shop-staff role.</p>
            </div>
          </div>
          {staffPermissionsQuery.isPending ? (
            <div className="loading-panel"><LoaderCircle className="spin" size={19} /> Loading permissions…</div>
          ) : staffPermissionsQuery.isError ? (
            <p className="form-alert" role="alert">
              {staffPermissionsQuery.error instanceof ApiError
                ? staffPermissionsQuery.error.message
                : "Unable to load staff permissions."}
            </p>
          ) : (
            <fieldset className="permission-list">
              <legend>Allowed actions</legend>
              {staffPermissionsQuery.data.permissions.map((permission) => (
                <label className="permission-option" key={permission.id}>
                  <input
                    checked={selectedPermissions.includes(permission.id)}
                    disabled={permissionsMutation.isPending}
                    onChange={(event) => {
                      setSelectedPermissions((current) =>
                        event.target.checked
                          ? [...current, permission.id]
                          : current.filter((value) => value !== permission.id),
                      );
                    }}
                    type="checkbox"
                  />
                  <span><strong>{permission.id.replaceAll(":", " · ")}</strong><small>{permission.description}</small></span>
                </label>
              ))}
            </fieldset>
          )}
          {permissionError && <p className="form-alert" role="alert">{permissionError}</p>}
          {staffPermissionsQuery.data && (
            <div className="settings-card-footer">
              <span className="settings-hint">Owner-only permissions cannot be granted to staff.</span>
              <button
                className="button button-primary"
                disabled={
                  permissionsMutation.isPending ||
                  (staffPermissionsQuery.data.permissions.every(
                    (permission) => permission.granted === selectedPermissions.includes(permission.id),
                  ))
                }
                onClick={() => permissionsMutation.mutate(selectedPermissions)}
                type="button"
              >
                {permissionsMutation.isPending && <LoaderCircle className="spin" size={16} />}
                Save staff access
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
