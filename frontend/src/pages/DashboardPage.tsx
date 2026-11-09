import { ArrowRight, BadgeCheck, CircleHelp, Settings2, ShieldCheck, ShoppingBag } from "lucide-react";
import { Link } from "react-router-dom";
import { hasPermission } from "../lib/permissions";
import type { User } from "../types";

interface DashboardPageProps {
  user: User;
}

const foundationSteps = [
  { title: "Secure access", detail: "Your staff account and permissions are active.", icon: ShieldCheck, complete: true },
  { title: "Business profile", detail: "Confirm your business details and payment methods.", icon: Settings2, complete: false },
  { title: "Products and stock", detail: "Add the products you sell and record opening stock.", icon: BadgeCheck, complete: false },
];

export function DashboardPage({ user }: DashboardPageProps) {
  const canManageSettings = hasPermission(user, "settings:manage");
  const canManageInventory = hasPermission(user, "inventory:manage");
  const today = new Intl.DateTimeFormat("en-NG", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "Africa/Lagos",
  }).format(new Date());
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
          Reports distinguish invoice totals, manually recorded payments, and balances due.
          Payment entries are not independently verified by a bank or payment provider.
        </p>
      </div>
    </div>
  );
}
