import { zodResolver } from "@hookform/resolvers/zod";
import { KeyRound } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { Brand } from "../components/Brand";
import { PasswordInput } from "../components/PasswordInput";
import { ApiError, api } from "../lib/api";

const schema = z.object({
  setup_token: z.string().min(32, "Enter the setup key provided by your administrator."),
  full_name: z.string().trim().min(1, "Enter your name.").max(160),
  phone: z.string().trim().min(7, "Enter your phone number.").max(40),
  email: z.union([z.email("Enter a valid email address."), z.literal("")]),
  password: z.string().min(12, "Use at least 12 characters.").max(128),
  confirm_password: z.string().min(1, "Confirm your password."),
}).refine((values) => values.password === values.confirm_password, {
  message: "Passwords do not match.",
  path: ["confirm_password"],
});

type Values = z.infer<typeof schema>;

export function OwnerSetupPage() {
  const setupStatus = useQuery({
    queryKey: ["owner-setup-status"],
    queryFn: api.ownerSetupStatus,
    retry: false,
  });
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);
  const form = useForm<Values>({ resolver: zodResolver(schema) });

  const submit = form.handleSubmit(async ({ setup_token, full_name, phone, email, password }) => {
    setError("");
    try {
      await api.setupOwner({ setup_token, full_name, phone, email: email || null, password });
      setComplete(true);
      await setupStatus.refetch();
    } catch (reason) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : "Unable to complete setup. Check your connection and try again.",
      );
    }
  });

  const enabled = setupStatus.data?.enabled === true;

  return (
    <main className="auth-page">
      <section className="auth-brand-panel" aria-label="MJD Square">
        <div className="auth-brand-content">
          <Brand />
          <div className="auth-message">
            <span className="eyebrow eyebrow-light">FIRST-TIME SETUP</span>
            <h1>Set up your business workspace.</h1>
            <p>Create the owner account for this deployment. The setup key is provided by your deployment administrator.</p>
          </div>
          <div className="auth-footnote"><span className="status-dot" />A secure workspace for your business</div>
        </div>
      </section>
      <section className="auth-form-panel">
        <div className="auth-form-wrap">
          <div className="auth-mobile-brand"><Brand /></div>
          <div className="auth-heading">
            <span className="auth-icon"><KeyRound size={19} /></span>
            <span className="eyebrow">OWNER ACCOUNT</span>
            <h2>{complete ? "Workspace ready" : "Create the first owner account"}</h2>
            <p>
              {complete
                ? "Your owner account is ready. Sign in with the phone number and password you just created."
                : "This one-time setup is available only on a fresh deployment."}
            </p>
          </div>
          {setupStatus.isPending ? (
            <p role="status">Checking setup availability…</p>
          ) : setupStatus.isError ? (
            <div className="form-stack">
              <p className="form-alert" role="alert">Unable to check setup availability. Please retry.</p>
              <button
                className="button button-secondary"
                disabled={setupStatus.isFetching}
                onClick={() => void setupStatus.refetch()}
                type="button"
              >
                Retry
              </button>
            </div>
          ) : complete ? (
            <div className="form-stack">
              <p className="success-alert" role="status">Owner account created successfully.</p>
              <Link className="button button-primary button-wide auth-button-link" to="/sign-in">
                Continue to sign in
              </Link>
            </div>
          ) : !enabled ? (
            <div className="form-stack">
              <p className="form-alert" role="status">First-time setup is closed. Sign in with an existing account.</p>
              <Link className="button button-primary button-wide auth-button-link" to="/sign-in">
                Back to sign in
              </Link>
            </div>
          ) : (
            <form className="form-stack" onSubmit={submit} noValidate>
              <label className="field">
                <span>One-time setup key</span>
                <PasswordInput
                  autoComplete="off"
                  aria-invalid={Boolean(form.formState.errors.setup_token)}
                  placeholder="Provided by your deployment administrator"
                  {...form.register("setup_token")}
                />
                {form.formState.errors.setup_token && <small className="field-error">{form.formState.errors.setup_token.message}</small>}
              </label>
              <label className="field">
                <span>Your name</span>
                <input autoComplete="name" aria-invalid={Boolean(form.formState.errors.full_name)} {...form.register("full_name")} />
                {form.formState.errors.full_name && <small className="field-error">{form.formState.errors.full_name.message}</small>}
              </label>
              <label className="field">
                <span>Phone number</span>
                <input autoComplete="tel" inputMode="tel" type="tel" aria-invalid={Boolean(form.formState.errors.phone)} {...form.register("phone")} />
                {form.formState.errors.phone && <small className="field-error">{form.formState.errors.phone.message}</small>}
              </label>
              <label className="field">
                <span>Email address (optional)</span>
                <input autoComplete="email" inputMode="email" type="email" aria-invalid={Boolean(form.formState.errors.email)} {...form.register("email")} />
                {form.formState.errors.email && <small className="field-error">{form.formState.errors.email.message}</small>}
                <small className="field-help">Password recovery is only available when an email address is provided.</small>
              </label>
              <label className="field">
                <span>Password</span>
                <PasswordInput
                  autoComplete="new-password"
                  aria-invalid={Boolean(form.formState.errors.password)}
                  placeholder="At least 12 characters"
                  {...form.register("password")}
                />
                {form.formState.errors.password && <small className="field-error">{form.formState.errors.password.message}</small>}
              </label>
              <label className="field">
                <span>Confirm password</span>
                <PasswordInput
                  autoComplete="new-password"
                  aria-invalid={Boolean(form.formState.errors.confirm_password)}
                  placeholder="Enter your password again"
                  {...form.register("confirm_password")}
                />
                {form.formState.errors.confirm_password && <small className="field-error">{form.formState.errors.confirm_password.message}</small>}
              </label>
              {error && <p className="form-alert" role="alert">{error}</p>}
              <button className="button button-primary button-wide" disabled={form.formState.isSubmitting} type="submit">
                {form.formState.isSubmitting ? "Creating owner account…" : "Create owner account"}
              </button>
            </form>
          )}
          {!complete && <Link className="auth-back-link" to="/sign-in">Back to sign in</Link>}
        </div>
      </section>
    </main>
  );
}
