import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { SignInPage } from "./components/SignInPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { DashboardPage } from "./pages/DashboardPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TeamPage } from "./pages/TeamPage";
import { AccountPage } from "./pages/AccountPage";
import { CustomersPage } from "./pages/CustomersPage";
import { InventoryPage } from "./pages/InventoryPage";
import { SuppliersPage } from "./pages/SuppliersPage";
import { SalesPage } from "./pages/SalesPage";
import { PurchasesPage } from "./pages/PurchasesPage";
import { ExpensesPage } from "./pages/ExpensesPage";
import { ReportsPage } from "./pages/ReportsPage";
import { PaymentRemindersPage } from "./pages/PaymentRemindersPage";
import { TransactionHistoryPage } from "./pages/TransactionHistoryPage";
import { api } from "./lib/api";
import { hasPermission } from "./lib/permissions";
import { ApiError } from "./lib/api";
import { LandingPage } from "./pages/LandingPage";
import { OwnerSetupPage } from "./pages/OwnerSetupPage";
import { ManualReceiptsPage } from "./pages/ManualReceiptsPage";

export default function App() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const sessionQuery = useQuery({
    queryKey: ["session"],
    queryFn: api.currentUser,
    enabled: location.pathname !== "/",
    retry: false,
  });

  if (location.pathname === "/") {
    return <LandingPage signedIn={Boolean(sessionQuery.data)} />;
  }

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
          path="/sign-in"
        />
        <Route element={<ForgotPasswordPage />} path="/forgot-password" />
        <Route element={<ResetPasswordPage />} path="/reset-password" />
        <Route element={<OwnerSetupPage />} path="/setup" />
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
        <Route element={<DashboardPage user={sessionQuery.data} />} path="/dashboard" />
        <Route
          element={
            hasPermission(sessionQuery.data, "customers:read")
              ? <CustomersPage user={sessionQuery.data} />
              : <Navigate replace to="/dashboard" />
          }
          path="/customers"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "suppliers:read")
              ? <SuppliersPage user={sessionQuery.data} />
              : <Navigate replace to="/dashboard" />
          }
          path="/suppliers"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "inventory:read")
              ? <InventoryPage user={sessionQuery.data} />
              : <Navigate replace to="/dashboard" />
          }
          path="/inventory"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "sales:read")
              ? <SalesPage user={sessionQuery.data} />
              : <Navigate replace to="/dashboard" />
          }
          path="/sales"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "payments:read")
              ? <ManualReceiptsPage user={sessionQuery.data} />
              : <Navigate replace to="/dashboard" />
          }
          path="/manual-receipts"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "purchases:read")
              ? <PurchasesPage user={sessionQuery.data} />
              : <Navigate replace to="/dashboard" />
          }
          path="/purchases"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "expenses:read")
              ? <ExpensesPage user={sessionQuery.data} />
              : <Navigate replace to="/dashboard" />
          }
          path="/expenses"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "reports:read")
              ? <ReportsPage user={sessionQuery.data} />
              : <Navigate replace to="/dashboard" />
          }
          path="/reports"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "customers:read")
              ? <PaymentRemindersPage />
              : <Navigate replace to="/dashboard" />
          }
          path="/payment-reminders"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "audit:read")
              ? <TransactionHistoryPage />
              : <Navigate replace to="/dashboard" />
          }
          path="/transaction-history"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "settings:read")
              ? <SettingsPage />
              : <Navigate replace to="/dashboard" />
          }
          path="/settings"
        />
        <Route
          element={
            hasPermission(sessionQuery.data, "staff:manage")
              ? <TeamPage />
              : <Navigate replace to="/dashboard" />
          }
          path="/team"
        />
        <Route element={<AccountPage />} path="/account" />
        <Route element={<Navigate replace to="/dashboard" />} path="*" />
      </Route>
      <Route element={<Navigate replace to="/dashboard" />} path="*" />
    </Routes>
  );
}
