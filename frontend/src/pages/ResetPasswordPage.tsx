import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, KeyRound } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { PasswordInput } from "../components/PasswordInput";
import { ApiError, api } from "../lib/api";
import { Brand } from "../components/Brand";

const schema = z.object({
  new_password: z.string().min(8, "Use at least 8 characters.").max(128, "Password must be 128 characters or fewer."),
  confirm_password: z.string().min(1, "Confirm your new password."),
}).refine((values) => values.new_password === values.confirm_password, {
  message: "Passwords do not match.",
  path: ["confirm_password"],
});
type Values = z.infer<typeof schema>;

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);
  const form = useForm<Values>({ resolver: zodResolver(schema) });

  const submit = form.handleSubmit(async ({ new_password }) => {
    setError("");
    try {
      await api.resetPassword(token, new_password);
      setComplete(true);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to reset your password. Please try again.");
    }
  });

  return (
    <main className="auth-page">
      <section className="auth-brand-panel" aria-label="MJD Square">
        <div className="auth-brand-content">
          <Brand />
          <div className="auth-message">
            <span className="eyebrow eyebrow-light">ACCOUNT SECURITY</span>
            <h1>A safer way back in.</h1>
            <p>Choose a new password to secure your MJD Square account.</p>
          </div>
          <div className="auth-footnote"><span className="status-dot" />A secure workspace for your business</div>
        </div>
      </section>
      <section className="auth-form-panel">
        <div className="auth-form-wrap">
          <div className="auth-mobile-brand"><Brand /></div>
          <div className="auth-heading">
            <span className="auth-icon"><KeyRound size={19} /></span>
            <span className="eyebrow">RESET PASSWORD</span>
            <h2>{complete ? "Password updated" : "Create a new password"}</h2>
            <p>{complete ? "Your password has been changed successfully." : "Choose a strong password you haven't used before."}</p>
          </div>
          {complete ? (
            <div className="form-stack">
              <p className="success-alert" role="status">Your password has been reset. You can now sign in.</p>
              <Link className="button button-primary button-wide auth-button-link" to="/">Continue to sign in</Link>
            </div>
          ) : !token ? (
            <div className="form-stack">
              <p className="form-alert" role="alert">This password reset link is missing its token or is invalid. Request a new reset link to continue.</p>
              <Link className="button button-primary button-wide auth-button-link" to="/forgot-password">Request a new link</Link>
            </div>
          ) : (
            <form className="form-stack" onSubmit={submit} noValidate>
              <label className="field">
                <span>New password</span>
                <PasswordInput autoComplete="new-password" placeholder="At least 8 characters" aria-invalid={Boolean(form.formState.errors.new_password)} {...form.register("new_password")} />
                {form.formState.errors.new_password && <small className="field-error">{form.formState.errors.new_password.message}</small>}
              </label>
              <label className="field">
                <span>Confirm new password</span>
                <PasswordInput autoComplete="new-password" placeholder="Enter your new password again" aria-invalid={Boolean(form.formState.errors.confirm_password)} {...form.register("confirm_password")} />
                {form.formState.errors.confirm_password && <small className="field-error">{form.formState.errors.confirm_password.message}</small>}
              </label>
              {error && <p className="form-alert" role="alert">{error}</p>}
              <button className="button button-primary button-wide" disabled={form.formState.isSubmitting} type="submit">
                {form.formState.isSubmitting ? "Updating password…" : "Reset password"}
              </button>
            </form>
          )}
          <Link className="auth-back-link" to="/"><ArrowLeft size={15} /> Back to sign in</Link>
        </div>
      </section>
    </main>
  );
}
