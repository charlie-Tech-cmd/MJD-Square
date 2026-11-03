import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, KeyRound, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiError, api } from "../lib/api";

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password."),
    new_password: z.string().min(12, "Use at least 12 characters.").max(128),
    confirm_password: z.string().min(1, "Confirm your new password."),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: "Passwords do not match.",
    path: ["confirm_password"],
  });

type PasswordValues = z.infer<typeof passwordSchema>;

export function AccountPage() {
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const form = useForm<PasswordValues>({ resolver: zodResolver(passwordSchema) });

  const submit = form.handleSubmit(async ({ current_password, new_password }) => {
    setMessage("");
    setErrorMessage("");
    try {
      await api.changePassword(current_password, new_password);
      form.reset();
      setMessage("Password updated. Other active sessions have been signed out.");
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "Unable to update your password.");
    }
  });

  return (
    <div className="settings-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR ACCOUNT</span>
          <h1>Account security</h1>
          <p>Update your password and keep your MJD Square account secure.</p>
        </div>
      </div>
      <form className="settings-card password-card" onSubmit={submit}>
        <div className="settings-card-heading">
          <span className="settings-heading-icon"><KeyRound size={18} /></span>
          <div><h2>Change password</h2><p>Use a unique password with at least 12 characters.</p></div>
        </div>
        <div className="settings-fields password-fields">
          <label className="field">
            <span>Current password</span>
            <input autoComplete="current-password" type="password" {...form.register("current_password")} />
            {form.formState.errors.current_password && <small className="field-error">{form.formState.errors.current_password.message}</small>}
          </label>
          <label className="field">
            <span>New password</span>
            <input autoComplete="new-password" type="password" {...form.register("new_password")} />
            {form.formState.errors.new_password && <small className="field-error">{form.formState.errors.new_password.message}</small>}
          </label>
          <label className="field">
            <span>Confirm new password</span>
            <input autoComplete="new-password" type="password" {...form.register("confirm_password")} />
            {form.formState.errors.confirm_password && <small className="field-error">{form.formState.errors.confirm_password.message}</small>}
          </label>
        </div>
        {errorMessage && <p className="form-alert" role="alert">{errorMessage}</p>}
        {message && <p className="success-alert" role="status"><CheckCircle2 size={16} />{message}</p>}
        <div className="settings-card-footer">
          <span className="settings-hint">Changing your password signs out other active sessions.</span>
          <button className="button button-primary" disabled={form.formState.isSubmitting} type="submit">
            {form.formState.isSubmitting && <LoaderCircle className="spin" size={16} />}
            Update password
          </button>
        </div>
      </form>
    </div>
  );
}
