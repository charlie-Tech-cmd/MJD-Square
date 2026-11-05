import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api, ApiError } from "../lib/api";
import { Brand } from "./Brand";
import { PasswordInput } from "./PasswordInput";
import { Link } from "react-router-dom";

const signInSchema = z.object({
  email: z.email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});

type SignInValues = z.infer<typeof signInSchema>;

interface SignInPageProps {
  onSignedIn: () => void;
}

export function SignInPage({ onSignedIn }: SignInPageProps) {
  const [serverError, setServerError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignInValues>({ resolver: zodResolver(signInSchema) });

  const submit = async ({ email, password }: SignInValues) => {
    setServerError("");
    try {
      await api.login(email, password);
      onSignedIn();
    } catch (error) {
      setServerError(
        error instanceof ApiError
          ? error.message
          : "Unable to connect. Check your connection and try again.",
      );
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-brand-panel" aria-label="MJD Square">
        <div className="auth-brand-content">
          <Brand />
          <div className="auth-message">
            <span className="eyebrow eyebrow-light">BUSINESS, IN GOOD ORDER</span>
            <h1>Know your business.<br />Run it with confidence.</h1>
            <p>
              One clear view of your shop operations, built for the way MJD Square works.
            </p>
          </div>
          <div className="auth-footnote">
            <span className="status-dot" />
            A secure workspace for your business
          </div>
        </div>
      </section>
      <section className="auth-form-panel">
        <div className="auth-form-wrap">
          <div className="auth-mobile-brand"><Brand /></div>
          <div className="auth-heading">
            <span className="auth-icon"><LockKeyhole size={19} /></span>
            <span className="eyebrow">WELCOME BACK</span>
            <h2>Sign in to your account</h2>
            <p>Use your MJD Square staff account to continue.</p>
          </div>
          <form className="form-stack" onSubmit={handleSubmit(submit)} noValidate>
            <label className="field">
              <span>Email address</span>
              <input
                autoComplete="username"
                inputMode="email"
                placeholder="you@mjdsquare.com"
                type="email"
                aria-invalid={Boolean(errors.email)}
                {...register("email")}
              />
              {errors.email && <small className="field-error">{errors.email.message}</small>}
            </label>
            <label className="field">
              <span>Password</span>
              <PasswordInput
                autoComplete="current-password"
                placeholder="Enter your password"
                aria-invalid={Boolean(errors.password)}
                {...register("password")}
              />
              <Link className="auth-inline-link" to="/forgot-password">Forgot password?</Link>
              {errors.password && <small className="field-error">{errors.password.message}</small>}
            </label>
            {serverError && <p className="form-alert" role="alert">{serverError}</p>}
            <button className="button button-primary button-wide" disabled={isSubmitting} type="submit">
              <span>{isSubmitting ? "Signing in..." : "Sign in"}</span>
              {!isSubmitting && <ArrowRight size={17} />}
            </button>
          </form>
          <p className="auth-security-note">Access is protected and monitored for your security.</p>
        </div>
      </section>
    </main>
  );
}
