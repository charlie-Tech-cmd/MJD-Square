import { Activity, LoaderCircle, Search } from "lucide-react";
import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import type { TransactionHistoryEntry } from "../types";

function formatAction(action: string): string {
  return action.replaceAll(".", " ").replaceAll("_", " ");
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-NG", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Africa/Lagos",
  }).format(new Date(value));
}

function detailValue(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (typeof value === "object") return null;
  return String(value);
}

function HistoryEntry({ entry }: { entry: TransactionHistoryEntry }) {
  const details = Object.entries(entry.details)
    .map(([key, value]) => ({ key, value: detailValue(value) }))
    .filter((item): item is { key: string; value: string } => item.value !== null);
  return (
    <article className="history-entry">
      <div className="history-entry-marker"><Activity size={15} /></div>
      <div className="history-entry-content">
        <div className="history-entry-heading">
          <strong>{formatAction(entry.action)}</strong>
          <time dateTime={entry.created_at}>{formatDateTime(entry.created_at)}</time>
        </div>
        <p>
          {entry.actor_name ?? "Former user"} · {entry.entity_type}
          {entry.entity_id ? ` · ${entry.entity_id}` : ""}
        </p>
        {details.length > 0 && (
          <dl className="history-details">
            {details.map(({ key, value }) => (
              <div key={key}>
                <dt>{key.replaceAll("_", " ")}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </article>
  );
}

export function TransactionHistoryPage() {
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const historyQuery = useInfiniteQuery({
    queryKey: ["transaction-history", query],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => api.transactionHistory(query, pageParam),
    getNextPageParam: (lastPage, pages) =>
      lastPage.length === 200 ? pages.length * 200 : undefined,
  });
  const entries = historyQuery.data?.pages.flat() ?? [];

  return (
    <div className="settings-page records-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">AUDIT TRAIL</span>
          <h1>Transaction history</h1>
          <p>Review recorded business transactions and important account, inventory, and access changes.</p>
        </div>
      </div>
      <form className="history-search" onSubmit={(event) => {
        event.preventDefault();
        setQuery(draftQuery.trim());
      }}>
        <label className="field">
          <span>Search history</span>
          <input
            placeholder="Search action, record type, or record ID"
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
          />
        </label>
        <button className="button button-primary" type="submit"><Search size={15} /> Search</button>
      </form>

      {historyQuery.isPending ? (
        <div className="loading-panel"><LoaderCircle className="spin" size={20} /> Loading transaction history…</div>
      ) : historyQuery.isError ? (
        <p className="form-alert" role="alert">
          {historyQuery.error instanceof ApiError ? historyQuery.error.message : "Unable to load transaction history."}
        </p>
      ) : entries.length === 0 ? (
        <section className="settings-card reminder-empty">
          <h2>No matching history</h2>
          <p>Recorded transactions and account events will appear here.</p>
        </section>
      ) : (
        <section className="settings-card history-card" aria-label="Transaction history">
          <div className="history-list">
            {entries.map((entry) => <HistoryEntry entry={entry} key={entry.id} />)}
          </div>
          <p className="history-limit-note">
            Showing {entries.length} audit event{entries.length === 1 ? "" : "s"}.
          </p>
          {historyQuery.hasNextPage && (
            <button
              className="button button-secondary"
              disabled={historyQuery.isFetchingNextPage}
              onClick={() => void historyQuery.fetchNextPage()}
              type="button"
            >
              {historyQuery.isFetchingNextPage
                ? <LoaderCircle className="spin" size={15} />
                : <Activity size={15} />}
              Load older transactions
            </button>
          )}
        </section>
      )}
    </div>
  );
}
