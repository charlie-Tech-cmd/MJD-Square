import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Mail } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { Brand } from "../components/Brand";

const schema = z.object({ email: z.email("Enter a valid email address.") });
type Values = z.infer<typeof schema>;

export function ForgotPasswordPage() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const form = useForm<Values>({ resolver: zodResolver(schema) });

  const submit = form.handleSubmit(async ({ email }) => {
    setMessage("");
    setError("");
    try {
      const result = await api.requestPasswordReset(email);
      setMessage(result.message);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to submit your request. Please try again.");
    }
  });

  return (
    <main className="auth-page">
      <section className="auth-brand-panel" aria-label="MJD Square">
        <div className="auth-brand-content">
          <Brand />
          <div className="auth-message">
            <span className="eyebrow eyebrow-light">ACCOUNT RECOVERY</span>
            <h1>Get back to business.</h1>
            <p>We'll help you securely regain access to your MJD Square workspace.</p>
          </div>
          <div className="auth-footnote"><span className="status-dot" />A secure workspace for your business</div>
        </div>
      </section>
      <section className="auth-form-panel">
        <div className="auth-form-wrap">
          <div className="auth-mobile-brand"><Brand /></div>
          <div className="auth-heading">
            <span className="auth-icon"><Mail size={19} /></span>
            <span className="eyebrow">PASSWORD RECOVERY</span>
            <h2>Forgot your password?</h2>
            <p>Enter the email address associated with your account.</p>
          </div>
          <form className="form-stack" onSubmit={submit} noValidate>
            <label className="field">
              <span>Email address</span>
              <input autoComplete="email" inputMode="email" placeholder="you@mjdsquare.com" type="email" aria-invalid={Boolean(form.formState.errors.email)} {...form.register("email")} />
              {form.formState.errors.email && <small className="field-error">{form.formState.errors.email.message}</small>}
            </label>
            {error && <p className="form-alert" role="alert">{error}</p>}
            {message && <p className="success-alert" role="status">{message}</p>}
            <button className="button button-primary button-wide" disabled={form.formState.isSubmitting} type="submit">
              {form.formState.isSubmitting ? "Sending instructions…" : "Send reset instructions"}
            </button>
          </form>
          <Link className="auth-back-link" to="/sign-in"><ArrowLeft size={15} /> Back to sign in</Link>
        </div>
      </section>
    </main>
  );
}
