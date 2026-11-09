import { zodResolver } from "@hookform/resolvers/zod";
import { BellRing, LoaderCircle, MessageCircle, Phone } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { formatNaira } from "../lib/format";
import type { PaymentReminder, ReminderStatus } from "../types";

const todayInBusinessTimezone = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Lagos" }).format(new Date());

const reminderSchema = z.object({
  status: z.enum(["prepared", "sent_manually", "follow_up_required", "promised_payment", "disputed"]),
  channel: z.enum(["whatsapp", "phone", "in_person", "other"]),
  notes: z.string().max(500),
});

type ReminderValues = z.infer<typeof reminderSchema>;

const statusLabels: Record<ReminderStatus, string> = {
  prepared: "Reminder prepared",
  sent_manually: "Sent manually",
  follow_up_required: "Follow-up required",
  promised_payment: "Customer promised payment",
  disputed: "Disputed",
  resolved: "Resolved",
};

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-NG", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Africa/Lagos",
  }).format(new Date(value));
}

function whatsappUrl(reminder: PaymentReminder): string | null {
  const rawNumber = reminder.customer_whatsapp ?? reminder.customer_phone;
  if (!rawNumber) return null;
  let number = rawNumber.replace(/\D/g, "");
  if (number.startsWith("0")) number = `234${number.slice(1)}`;
  if (number.length < 8 || number.length > 15) return null;
  const message = [
    `Hello ${reminder.customer_name},`,
    `This is a payment reminder from MJD Square for invoice ${reminder.invoice_number}.`,
    `Invoice amount: ${formatNaira(reminder.total_amount)}.`,
    `Amount paid: ${formatNaira(reminder.amount_paid)}.`,
    `Outstanding balance: ${formatNaira(reminder.balance_due)}.`,
    `Due date: ${reminder.due_date}.`,
    "Please contact us if you have already made this payment. Thank you.",
  ].join("\n");
  return `https://wa.me/${number}?text=${encodeURIComponent(message)}`;
}

function ReminderCard({ reminder }: { reminder: PaymentReminder }) {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const form = useForm<ReminderValues>({
    resolver: zodResolver(reminderSchema),
    defaultValues: {
      status: reminder.latest_status && reminder.latest_status !== "resolved"
        ? reminder.latest_status
        : "prepared",
      channel: "whatsapp",
      notes: "",
    },
  });
  const mutation = useMutation({
    mutationFn: (values: ReminderValues) => api.recordReminderActivity(reminder.sale_id, {
      status: values.status,
      channel: values.status === "sent_manually" ? values.channel : null,
      notes: values.notes.trim(),
    }),
    onSuccess: async () => {
      setFeedback("Reminder activity saved.");
      form.reset({ status: "prepared", channel: "whatsapp", notes: "" });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["payment-reminders"] }),
        queryClient.invalidateQueries({ queryKey: ["transaction-history"] }),
      ]);
    },
    onError: (error) => setFeedback(
      error instanceof ApiError ? error.message : "Unable to save reminder activity.",
    ),
  });

  const today = todayInBusinessTimezone();
  const overdue = reminder.due_date < today;
  const dueLabel = overdue
    ? `${reminder.days_overdue} day${reminder.days_overdue === 1 ? "" : "s"} overdue`
    : reminder.due_date === today
      ? "Due today"
      : `Due ${reminder.due_date}`;
  const preparedUrl = whatsappUrl(reminder);

  return (
    <article className="settings-card reminder-card">
      <div className="reminder-card-heading">
        <div className="record-details">
          <strong>{reminder.invoice_number} · {reminder.customer_name}</strong>
          <small>Issued {reminder.sale_date} · Due {reminder.due_date}</small>
        </div>
        <span className={`reminder-due-badge${overdue ? " is-overdue" : ""}`}>
          {dueLabel}
        </span>
      </div>
      <div className="reminder-summary">
        <div><span>Invoice total</span><strong>{formatNaira(reminder.total_amount)}</strong></div>
        <div><span>Paid</span><strong>{formatNaira(reminder.amount_paid)}</strong></div>
        <div><span>Outstanding</span><strong>{formatNaira(reminder.balance_due)}</strong></div>
      </div>
      <div className="reminder-contact-row">
        <span>
          {reminder.latest_status
            ? statusLabels[reminder.latest_status]
            : "Not contacted"}
          {reminder.last_contacted_at && ` · Last contacted ${formatDateTime(reminder.last_contacted_at)}`}
        </span>
        {preparedUrl ? (
          <a className="button button-secondary record-action" href={preparedUrl} rel="noreferrer" target="_blank">
            <MessageCircle size={14} /> Prepare WhatsApp
          </a>
        ) : reminder.customer_phone ? (
          <a className="button button-secondary record-action" href={`tel:${reminder.customer_phone}`}>
            <Phone size={14} /> Call customer
          </a>
        ) : <span className="settings-hint">No customer phone number</span>}
      </div>
      {reminder.activities.length > 0 && (
        <details className="reminder-activity-list">
          <summary>{reminder.activities.length} recorded reminder {reminder.activities.length === 1 ? "activity" : "activities"}</summary>
          {reminder.activities.map((activity) => (
            <div className="reminder-activity-item" key={activity.id}>
              <span><strong>{statusLabels[activity.status]}</strong>{activity.channel && ` · ${activity.channel.replace("_", " ")}`}</span>
              <small>{activity.actor_name ?? "Former user"} · {formatDateTime(activity.created_at)}{activity.notes && ` · ${activity.notes}`}</small>
            </div>
          ))}
        </details>
      )}
      <form className="reminder-activity-form" onSubmit={form.handleSubmit((values) => {
        setFeedback("");
        mutation.mutate(values);
      })}>
        <label className="field">
          <span>Update follow-up status</span>
          <select {...form.register("status")}>
            <option value="prepared">Reminder prepared</option>
            <option value="sent_manually">Sent manually</option>
            <option value="follow_up_required">Follow-up required</option>
            <option value="promised_payment">Customer promised payment</option>
            <option value="disputed">Disputed</option>
          </select>
        </label>
        {form.watch("status") === "sent_manually" && (
          <label className="field">
            <span>Contact channel</span>
            <select {...form.register("channel")}>
              <option value="whatsapp">WhatsApp</option>
              <option value="phone">Phone</option>
              <option value="in_person">In person</option>
              <option value="other">Other</option>
            </select>
          </label>
        )}
        <label className="field reminder-notes-field">
          <span>Notes (optional)</span>
          <input placeholder="Add a short follow-up note" {...form.register("notes")} />
        </label>
        <button className="button button-primary record-action" disabled={mutation.isPending} type="submit">
          {mutation.isPending ? <LoaderCircle className="spin" size={14} /> : <BellRing size={14} />}
          Save activity
        </button>
      </form>
      {feedback && (
        <p className={mutation.isError ? "form-alert" : "success-alert"} role={mutation.isError ? "alert" : "status"}>
          {feedback}
        </p>
      )}
    </article>
  );
}

export function PaymentRemindersPage() {
  const remindersQuery = useQuery({
    queryKey: ["payment-reminders"],
    queryFn: api.paymentReminders,
  });

  if (remindersQuery.isPending) {
    return <div className="loading-panel"><LoaderCircle className="spin" size={20} /> Loading payment reminders…</div>;
  }
  if (remindersQuery.isError) {
    return <p className="form-alert" role="alert">
      {remindersQuery.error instanceof ApiError ? remindersQuery.error.message : "Unable to load payment reminders."}
    </p>;
  }

  const today = todayInBusinessTimezone();
  const reminders = remindersQuery.data;
  const overdueCount = reminders.filter((reminder) => reminder.due_date < today).length;
  const dueTodayCount = reminders.filter((reminder) => reminder.due_date === today).length;
  const upcomingCount = reminders.filter((reminder) => {
    const daysUntilDue = Math.ceil(
      (new Date(`${reminder.due_date}T00:00:00`).getTime() - new Date(`${today}T00:00:00`).getTime())
      / 86_400_000,
    );
    return daysUntilDue > 0 && daysUntilDue <= 7;
  }).length;

  return (
    <div className="settings-page records-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">CUSTOMER FOLLOW-UP</span>
          <h1>Payment reminders</h1>
          <p>Review upcoming and overdue customer invoices, prepare a message, and record follow-up activity.</p>
        </div>
      </div>
      <p className="dashboard-note">
        Opening WhatsApp only prepares a message for staff review; it does not send or confirm delivery.
        Mark a reminder as sent manually only after you have sent it.
      </p>
      <div className="reminder-stat-grid">
        <article className="report-card"><span>Overdue invoices</span><strong>{overdueCount}</strong><small>Past the stated due date</small></article>
        <article className="report-card"><span>Due today</span><strong>{dueTodayCount}</strong><small>Outstanding invoices due today</small></article>
        <article className="report-card"><span>Due in 7 days</span><strong>{upcomingCount}</strong><small>Upcoming customer follow-ups</small></article>
      </div>
      {reminders.length === 0 ? (
        <section className="settings-card reminder-empty">
          <h2>No outstanding customer invoices</h2>
          <p>Invoices with a remaining balance will appear here for follow-up.</p>
        </section>
      ) : (
        <div className="reminder-list">
          {reminders.map((reminder) => <ReminderCard key={reminder.sale_id} reminder={reminder} />)}
        </div>
      )}
    </div>
  );
}
