import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BadgeCheck,
  CircleHelp,
  LoaderCircle,
  Settings2,
  ShieldCheck,
  ShoppingBag,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import { formatNaira } from "../lib/format";
import { hasPermission } from "../lib/permissions";
import type { DashboardSummary, User } from "../types";

interface DashboardPageProps {
  user: User;
}

type Period = "7_days" | "30_days" | "year_to_date";

const foundationSteps = [
  { title: "Secure access", detail: "Your staff account and permissions are active.", icon: ShieldCheck, complete: true },
  { title: "Business profile", detail: "Confirm your business details and payment methods.", icon: Settings2, complete: false },
  { title: "Products and stock", detail: "Add the products you sell and record opening stock.", icon: BadgeCheck, complete: false },
];

function businessDate(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Lagos",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function periodRange(period: Period): { from: string; to: string } {
  const to = businessDate(new Date());
  if (period === "year_to_date") return { from: `${to.slice(0, 4)}-01-01`, to };
  const from = new Date(`${to}T00:00:00Z`);
  from.setUTCDate(from.getUTCDate() - (period === "7_days" ? 6 : 29));
  return { from: from.toISOString().slice(0, 10), to };
}

function actionLabel(action: string): string {
  return action.replaceAll(".", " ").replaceAll("_", " ");
}

function SalesTrend({ summary }: { summary: DashboardSummary }) {
  const maxSales = Math.max(...summary.sales_trend.map(({ sales_total }) => Number(sales_total)), 0);
  return (
    <section className="settings-card dashboard-panel">
      <div className="section-heading">
        <div><span className="eyebrow">SALES ACTIVITY</span><h2>Sales trend</h2></div>
      </div>
      {summary.sales_trend.every(({ sales_total }) => Number(sales_total) === 0) ? (
        <p className="settings-hint">No sales were recorded in this period.</p>
      ) : (
        <div className="dashboard-trend" role="img" aria-label="Daily sales trend">
          {summary.sales_trend.map(({ date, sales_total }) => (
            <div className="dashboard-trend-day" key={date} title={`${date}: ${formatNaira(sales_total)}`}>
              <span
                className="dashboard-trend-bar"
                style={{ height: `${Math.max((Number(sales_total) / maxSales) * 100, 2)}%` }}
              />
              <small>{date.slice(5)}</small>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function DashboardPage({ user }: DashboardPageProps) {
  const canManageSettings = hasPermission(user, "settings:manage");
  const canManageInventory = hasPermission(user, "inventory:manage");
  const canViewFinancials = hasPermission(user, "reports:read");
  const [period, setPeriod] = useState<Period>("30_days");
  const { from, to } = periodRange(period);
  const summaryQuery = useQuery({
    queryKey: ["dashboard", "summary", from, to],
    queryFn: () => api.dashboardSummary(from, to),
    enabled: canViewFinancials,
  });
  const today = new Intl.DateTimeFormat("en-NG", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "Africa/Lagos",
  }).format(new Date());
  const summary = summaryQuery.data;

  return (
    <div className="dashboard-page">
      <div className="page-heading dashboard-heading">
        <div>
          <span className="eyebrow">{today.toUpperCase()}</span>
          <h1>Welcome to MJD Square</h1>
          <p>Your workspace is ready. Check stock, record a sale, or review your business activity.</p>
        </div>
        <div className="dashboard-actions">
          {hasPermission(user, "sales:create") && (
            <Link className="button button-primary" to="/sales"><ShoppingBag size={16} /> Record a sale</Link>
          )}
          {canManageSettings && (
            <Link className="button button-secondary" to="/settings"><Settings2 size={16} /> Business settings</Link>
          )}
        </div>
      </div>

      {canViewFinancials && (
        <section aria-label="Business performance" className="dashboard-financials">
          <div className="section-heading dashboard-period-heading">
            <div>
              <span className="eyebrow">BUSINESS PERFORMANCE</span>
              <h2>Financial overview</h2>
              <p>{from} to {to}</p>
            </div>
            <div aria-label="Dashboard date range" className="dashboard-periods">
              {([
                ["7_days", "7 days"],
                ["30_days", "30 days"],
                ["year_to_date", "Year to date"],
              ] as const).map(([value, label]) => (
                <button
                  aria-pressed={period === value}
                  className={`button ${period === value ? "button-primary" : "button-secondary"}`}
                  key={value}
                  onClick={() => setPeriod(value)}
                  type="button"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {summaryQuery.isError && (
            <p className="form-alert" role="alert">
              {summaryQuery.error instanceof ApiError
                ? summaryQuery.error.message
                : "Unable to load dashboard metrics."}
            </p>
          )}
          {summaryQuery.isPending ? (
            <div className="loading-panel"><LoaderCircle className="spin" size={20} /> Loading dashboard…</div>
          ) : summary && (
            <>
              <div className="report-grid">
                <article className="report-card"><span>Sales invoiced</span><strong>{formatNaira(summary.sales_total)}</strong><small>For selected dates</small></article>
                <article className="report-card"><span>Payments received</span><strong>{formatNaira(summary.payments_received)}</strong><small>Manual records; not bank-verified</small></article>
                <article className="report-card"><span>Purchases</span><strong>{formatNaira(summary.purchases_total)}</strong><small>Supplier invoices for selected dates</small></article>
                <article className="report-card"><span>Supplier payments</span><strong>{formatNaira(summary.payments_made)}</strong><small>Manual records for selected dates</small></article>
                <article className="report-card"><span>Expenses</span><strong>{formatNaira(summary.expenses_total)}</strong><small>Recorded outgoings for selected dates</small></article>
                <article className="report-card"><span>Customer receivables</span><strong>{formatNaira(summary.customer_receivables)}</strong><small>Current account balances</small></article>
                <article className="report-card"><span>Supplier payables</span><strong>{formatNaira(summary.supplier_payables)}</strong><small>Current account balances</small></article>
                <article className="report-card"><span>Inventory at recorded cost</span><strong>{formatNaira(summary.inventory_value_at_recorded_cost)}</strong><small>{summary.inventory_value_note}</small></article>
                <article className="report-card"><span>Low-stock products</span><strong>{summary.low_stock_count}</strong><small>Active products at or below minimum</small></article>
              </div>
              <div className="dashboard-detail-grid">
                <SalesTrend summary={summary} />
                <section className="settings-card dashboard-panel">
                  <div className="section-heading">
                    <div><span className="eyebrow">CUSTOMER INVOICES</span><h2>Overdue balance aging</h2></div>
                  </div>
                  <div className="dashboard-aging-list">
                    {([
                      ["1_30_days", "1–30 days"],
                      ["31_60_days", "31–60 days"],
                      ["61_90_days", "61–90 days"],
                      ["over_90_days", "Over 90 days"],
                    ] as const).map(([key, label]) => (
                      <div className="dashboard-aging-row" key={key}>
                        <span>{label}</span>
                        <strong>{formatNaira(summary.overdue_invoice_buckets[key])}</strong>
                      </div>
                    ))}
                  </div>
                  <p className="settings-hint">{summary.aging_note}</p>
                </section>
                <section className="settings-card dashboard-panel">
                  <div className="section-heading">
                    <div><span className="eyebrow">BEST SELLERS</span><h2>Top products</h2></div>
                    {hasPermission(user, "inventory:read") && <Link className="text-link" to="/inventory">Inventory <ArrowRight size={14} /></Link>}
                  </div>
                  {summary.top_products.length ? (
                    <div className="dashboard-list">
                      {summary.top_products.map((product) => (
                        <div className="dashboard-list-row" key={product.product_id}>
                          <span><strong>{product.product_name}</strong><small>{product.quantity_sold} sold</small></span>
                          <strong>{formatNaira(product.sales_total)}</strong>
                        </div>
                      ))}
                    </div>
                  ) : <p className="settings-hint">No products sold in this period.</p>}
                </section>
                <section className="settings-card dashboard-panel">
                  <div className="section-heading">
                    <div><span className="eyebrow">AUDIT TRAIL</span><h2>Recent activity</h2></div>
                    {hasPermission(user, "audit:read") && <Link className="text-link" to="/transaction-history">View history <ArrowRight size={14} /></Link>}
                  </div>
                  {summary.recent_activity.length ? (
                    <div className="dashboard-list">
                      {summary.recent_activity.map((activity) => (
                        <div className="dashboard-list-row" key={activity.id}>
                          <span><strong>{actionLabel(activity.action)}</strong><small>{activity.actor_name ?? "Former user"} · {new Date(activity.created_at).toLocaleString("en-NG")}</small></span>
                          {typeof activity.details.amount === "string" && <strong>{formatNaira(activity.details.amount)}</strong>}
                        </div>
                      ))}
                    </div>
                  ) : <p className="settings-hint">No recent business activity.</p>}
                </section>
              </div>
            </>
          )}
        </section>
      )}

      <section className="welcome-panel">
        <div className="welcome-copy">
          <span className="eyebrow eyebrow-light">A CLEARER VIEW OF YOUR BUSINESS</span>
          <h2>Everything in its right place.</h2>
          <p>
            Record completed sales, track payments against invoices, and keep stock movement tied to purchases.
            Your reports use the records your team enters.
          </p>
          {hasPermission(user, "sales:read") && (
            <Link className="welcome-link" to="/sales">
              Open sales and invoices <ArrowRight size={16} />
            </Link>
          )}
          {canManageSettings && !hasPermission(user, "sales:read") && (
            <Link className="welcome-link" to="/settings">
              Review business settings <ArrowRight size={16} />
            </Link>
          )}
        </div>
        <div className="welcome-graphic" aria-hidden="true">
          <div className="graphic-ring graphic-ring-one" />
          <div className="graphic-ring graphic-ring-two" />
          <div className="graphic-square"><span>M</span><i /></div>
        </div>
      </section>

      <div className="section-heading setup-section-heading">
        <div>
          <span className="eyebrow">GETTING STARTED</span>
          <h2>Your workspace setup</h2>
        </div>
        <span className="setup-progress">1 <span>of</span> 3 steps</span>
      </div>

      <section className="setup-grid" aria-label="Workspace setup">
        {foundationSteps.map((step, index) => {
          const Icon = step.icon;
          const content = (
            <>
              <div className={`setup-icon${step.complete ? " setup-icon-complete" : ""}`}>
                <Icon size={19} />
              </div>
              <span className="setup-number">0{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.detail}</p>
              <span className={`setup-status${step.complete ? " is-complete" : ""}`}>
                {step.complete ? "Complete" : "Next step"}
              </span>
            </>
          );
          return step.title === "Business profile" && canManageSettings ? (
            <Link className="setup-card setup-card-link" key={step.title} to="/settings">
              {content}
            </Link>
          ) : step.title === "Products and stock" && canManageInventory ? (
            <Link className="setup-card setup-card-link" key={step.title} to="/inventory">
              {content}
            </Link>
          ) : (
            <article className={`setup-card${step.complete ? " setup-card-done" : ""}`} key={step.title}>
              {content}
            </article>
          );
        })}
      </section>

      <div className="dashboard-note">
        <CircleHelp size={17} />
        <p>
          Financial metrics are available only to users with report access. Invoice aging excludes account payments
          that have not been allocated to specific invoices; estimates use manually recorded data.
        </p>
      </div>
    </div>
  );
}
