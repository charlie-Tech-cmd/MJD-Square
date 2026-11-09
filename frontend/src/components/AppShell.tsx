import {
  Activity,
  ArrowUpRight,
  BarChart3,
  BellRing,
  Boxes,
  BriefcaseBusiness,
  ChevronDown,
  CircleDollarSign,
  LayoutDashboard,
  KeyRound,
  Menu,
  PackageOpen,
  Settings,
  ShoppingBag,
  Users,
  UserRoundCog,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../lib/api";
import { hasPermission } from "../lib/permissions";
import { ApiError } from "../lib/api";
import type { User } from "../types";
import { Brand } from "./Brand";

const navItems = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard, permission: "dashboard:read", active: true },
  { label: "Sales & invoices", to: "/sales", icon: ShoppingBag, permission: "sales:read" },
  { label: "Customers", to: "/customers", icon: Users, permission: "customers:read" },
  { label: "Suppliers", to: "/suppliers", icon: BriefcaseBusiness, permission: "suppliers:read" },
  { label: "Products & inventory", to: "/inventory", icon: Boxes, permission: "inventory:read" },
  { label: "Purchases", to: "/purchases", icon: PackageOpen, permission: "purchases:read" },
  { label: "Expenses", to: "/expenses", icon: CircleDollarSign, permission: "expenses:read" },
  { label: "Payment reminders", icon: BellRing, permission: "customers:read" },
  { label: "Reports", to: "/reports", icon: BarChart3, permission: "reports:read" },
  { label: "Transaction history", icon: Activity, permission: "audit:read" },
];

interface AppShellProps {
  user: User;
  onSignOut: () => void;
}

export function AppShell({ user, onSignOut }: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const location = useLocation();

  const signOut = async () => {
    setLogoutError("");
    try {
      await api.logout();
      onSignOut();
    } catch (error) {
      setLogoutError(error instanceof ApiError ? error.message : "Unable to sign out. Please try again.");
    }
  };

  const sidebar = (
    <>
      <div className="sidebar-brand"><Brand /></div>
      <div className="workspace-switcher">
        <span className="workspace-avatar">M</span>
        <span className="workspace-copy">
          <strong>MJD Square</strong>
          <small>Business workspace</small>
        </span>
        <ChevronDown size={15} className="muted-icon" />
      </div>
      <nav className="side-nav" aria-label="Main navigation">
        <span className="nav-section-label">WORKSPACE</span>
        {navItems.filter((item) => hasPermission(user, item.permission)).map((item) => {
          const Icon = item.icon;
          if (!item.to) {
            return (
              <div className="nav-item nav-item-disabled" key={item.label} aria-disabled="true">
                <Icon size={17} strokeWidth={1.8} />
                <span>{item.label}</span>
                <small>Planned</small>
              </div>
            );
          }
          return (
            <NavLink
              className={({ isActive }) => `nav-item${isActive ? " nav-item-active" : ""}`}
              end
              key={item.label}
              onClick={() => setMobileNavOpen(false)}
              to={item.to}
            >
              <Icon size={17} strokeWidth={1.8} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
        <span className="nav-section-label nav-section-settings">ACCOUNT</span>
        {hasPermission(user, "settings:read") && (
          <NavLink
            className={({ isActive }) => `nav-item${isActive ? " nav-item-active" : ""}`}
            onClick={() => setMobileNavOpen(false)}
            to="/settings"
          >
            <Settings size={17} strokeWidth={1.8} />
            <span>Business settings</span>
          </NavLink>
        )}
        <NavLink
          className={({ isActive }) => `nav-item${isActive ? " nav-item-active" : ""}`}
          onClick={() => setMobileNavOpen(false)}
          to="/account"
        >
          <KeyRound size={17} strokeWidth={1.8} />
          <span>Account security</span>
        </NavLink>
        {hasPermission(user, "staff:manage") && (
          <NavLink
            className={({ isActive }) => `nav-item${isActive ? " nav-item-active" : ""}`}
            onClick={() => setMobileNavOpen(false)}
            to="/team"
          >
            <UserRoundCog size={17} strokeWidth={1.8} />
            <span>Staff & permissions</span>
          </NavLink>
        )}
      </nav>
      <div className="sidebar-bottom">
        <div className="phase-note">
          <span className="phase-note-icon"><Activity size={15} /></span>
          <div>
            <strong>Core operations ready</strong>
            <small>Sales, stock, and payables</small>
          </div>
          <ArrowUpRight size={15} className="muted-icon" />
        </div>
        <div className="profile-row">
          <span className="profile-avatar">{user.full_name.slice(0, 1).toUpperCase()}</span>
          <div className="profile-copy">
            <strong>{user.full_name}</strong>
            <small>{user.role.name}</small>
          </div>
          <button className="icon-button profile-menu" type="button" onClick={() => void signOut()} title="Sign out">
            <ChevronDown size={16} />
          </button>
        </div>
      </div>
    </>
  );

  const pageTitleByPath: Record<string, string> = {
    "/settings": "Business settings",
    "/team": "Staff and permissions",
    "/account": "Account security",
    "/customers": "Customers",
    "/suppliers": "Suppliers",
    "/inventory": "Products & inventory",
    "/sales": "Sales & invoices",
    "/purchases": "Purchases",
    "/expenses": "Expenses",
    "/reports": "Reports",
  };
  const pageTitle = pageTitleByPath[location.pathname] ?? "Dashboard";

  return (
    <div className="app-layout">
      {mobileNavOpen && (
        <button
          aria-label="Close navigation"
          className="mobile-backdrop"
          onClick={() => setMobileNavOpen(false)}
          type="button"
        />
      )}
      <aside className={`sidebar${mobileNavOpen ? " sidebar-open" : ""}`}>
        <button
          aria-label="Close navigation"
          className="mobile-close icon-button"
          onClick={() => setMobileNavOpen(false)}
          type="button"
        >
          <X size={19} />
        </button>
        {sidebar}
      </aside>
      <div className="main-column">
        <header className="topbar">
          <button
            aria-label="Open navigation"
            className="mobile-menu icon-button"
            onClick={() => setMobileNavOpen(true)}
            type="button"
          >
            <Menu size={20} />
          </button>
          <div className="breadcrumbs">
            <span>MJD Square</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{pageTitle}</strong>
          </div>
          <div className="topbar-right">
            {logoutError && <span className="logout-error" role="alert">{logoutError}</span>}
            <span className="today-pill"><span className="status-dot" /> Workspace active</span>
            <button className="profile-top" type="button" onClick={() => void signOut()} title="Sign out">
              <span className="profile-avatar">{user.full_name.slice(0, 1).toUpperCase()}</span>
              <ChevronDown size={14} />
            </button>
          </div>
        </header>
        <main className="page-content"><Outlet /></main>
        <footer className="app-footer">
          <span>MJD Square business management</span>
          <span>NGN <span className="footer-divider">·</span> Africa/Lagos</span>
        </footer>
      </div>
    </div>
  );
}
