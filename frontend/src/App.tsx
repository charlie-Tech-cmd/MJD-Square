import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { SignInPage } from "./components/SignInPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { DashboardPage } from "./pages/DashboardPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TeamPage } from "./pages/TeamPage";
import { AccountPage } from "./pages/AccountPage";
import { api } from "./lib/api";
import { hasPermission } from "./lib/permissions";
import { ApiError } from "./lib/api";

export default function App() {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({
    queryKey: ["session"],
    queryFn: api.currentUser,
    retry: false,
  });

  if (sessionQuery.isPending) {
    return <main className="splash-loading"><LoaderCircle className="spin" size={23} /> Checking your secure session…</main>;
  }
  if (sessionQuery.isError) {
    const message = sessionQuery.error instanceof ApiError
      ? sessionQuery.error.message
      : sessionQuery.error instanceof TypeError
        ? "Cannot connect to the MJD Square API. Start the backend and PostgreSQL, then retry."
        : "Session verification failed. Check the API service and retry.";
    return (
      <main className="splash-error" role="alert">
        <div className="splash-error-card">
          <strong>Unable to connect to your workspace</strong>
          <span>{message}</span>
          <button
            className="button button-secondary"
            disabled={sessionQuery.isFetching}
            onClick={() => void sessionQuery.refetch()}
            type="button"
          >
            {sessionQuery.isFetching ? "Retrying…" : "Retry"}
          </button>
        </div>
      </main>
    );
  }
  if (!sessionQuery.data) {
    return (
      <Routes>
        <Route
          element={
            <SignInPage
              onSignedIn={() =>
                void queryClient.invalidateQueries({ queryKey: ["session"] })
              }
            />
          }
          path="/"
        />
        <Route element={<ForgotPasswordPage />} path="/forgot-password" />
        <Route element={<ResetPasswordPage />} path="/reset-password" />
        <Route element={<Navigate replace to="/" />} path="*" />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route
        element={
          <AppShell
            user={sessionQuery.data}
            onSignOut={() => {
              queryClient.setQueryData(["session"], null);
              queryClient.clear();
            }}
          />
        }
      >
        <Route element={<DashboardPage user={sessionQuery.data} />} path="/" />
        <Route
          element={
            hasPermission(sessionQuery.data, "settings:read")
              ? <SettingsPage />
              : <Navigate replace to="/" />
          }
          path="/settings"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "staff:manage")
              ? <TeamPage />
              : <Navigate replace to="/" />
          }
          path="/team"
        />
        <Route element={<AccountPage />} path="/account" />
        <Route element={<Navigate replace to="/" />} path="*" />
      </Route>
    </Routes>
  );
}
