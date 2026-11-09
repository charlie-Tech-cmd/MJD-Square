import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, UserRoundPlus, Users } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { formatNaira } from "../lib/format";
import { hasPermission } from "../lib/permissions";
import type { Customer, User } from "../types";

const customerSchema = z.object({
  name: z.string().trim().min(1, "Enter the customer's name.").max(160),
  phone: z.string().max(40),
  whatsapp: z.string().max(40),
  email: z.union([z.email("Enter a valid email address."), z.literal("")]),
  address: z.string().max(500),
  customer_type: z.enum(["retail", "wholesale", "both"]),
  notes: z.string().max(5000),
  opening_balance: z.string().regex(/^\d{1,12}(?:\.\d{1,2})?$/, "Enter an amount with up to 2 decimal places."),
  opening_balance_date: z.string(),
  opening_balance_notes: z.string().max(500),
}).superRefine((values, context) => {
  const hasOpeningBalance = /[1-9]/.test(values.opening_balance);
  if (hasOpeningBalance && !values.opening_balance_date) {
    context.addIssue({ code: "custom", path: ["opening_balance_date"], message: "Choose the date for this opening balance." });
  }
  if (hasOpeningBalance && !values.opening_balance_notes.trim()) {
    context.addIssue({ code: "custom", path: ["opening_balance_notes"], message: "Add the source of this opening balance." });
  }
});

type CustomerValues = z.infer<typeof customerSchema>;

interface CustomersPageProps {
  user: User;
}

export function CustomersPage({ user }: CustomersPageProps) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const canRecordOpeningBalance = hasPermission(user, "customers:opening_balance");
  const customersQuery = useQuery({ queryKey: ["customers"], queryFn: api.customers });
  const form = useForm<CustomerValues>({
    resolver: zodResolver(customerSchema),
    defaultValues: {
      name: "",
      phone: "",
      whatsapp: "",
      email: "",
      address: "",
      customer_type: "retail",
      notes: "",
      opening_balance: "0.00",
      opening_balance_date: "",
      opening_balance_notes: "",
    },
  });
  const createMutation = useMutation({
    mutationFn: api.createCustomer,
    onSuccess: async () => {
      setActionError("");
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Unable to create customer.");
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: Parameters<typeof api.updateCustomer>[1] }) =>
      api.updateCustomer(id, changes),
    onSuccess: async () => {
      setActionError("");
      setEditingCustomer(null);
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Unable to update customer.");
    },
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.updateCustomer(id, { is_active }),
    onSuccess: async () => {
      setActionError("");
      await queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Unable to update customer.");
    },
  });

  const submit = form.handleSubmit((values) => {
    const fields = {
      name: values.name,
      phone: values.phone.trim() || null,
      whatsapp: values.whatsapp.trim() || null,
      email: values.email || null,
      address: values.address.trim() || null,
      customer_type: values.customer_type,
      notes: values.notes.trim(),
    };
    if (editingCustomer) {
      updateMutation.mutate({ id: editingCustomer.id, changes: fields });
    } else {
      createMutation.mutate({
        ...fields,
        opening_balance: canRecordOpeningBalance ? values.opening_balance : "0.00",
        opening_balance_date: canRecordOpeningBalance ? values.opening_balance_date || null : null,
        opening_balance_notes: canRecordOpeningBalance ? values.opening_balance_notes.trim() || null : null,
      });
    }
  });

  const editCustomer = (customer: Customer) => {
    setActionError("");
    setEditingCustomer(customer);
    form.reset({
      name: customer.name,
      phone: customer.phone ?? "",
      whatsapp: customer.whatsapp ?? "",
      email: customer.email ?? "",
      address: customer.address ?? "",
      customer_type: customer.customer_type,
      notes: customer.notes,
      opening_balance: "0.00",
      opening_balance_date: "",
      opening_balance_notes: "",
    });
  };

  return (
    <div className="settings-page records-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">BUSINESS RECORDS</span>
          <h1>Customers</h1>
          <p>Keep customer contact details and documented opening balances in one place.</p>
        </div>
      </div>
      <div className="records-layout">
        <form className="settings-card record-form-card" onSubmit={submit}>
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><UserRoundPlus size={18} /></span>
            <div><h2>{editingCustomer ? "Edit customer" : "Add customer"}</h2><p>Customer balances start with documented opening entries.</p></div>
          </div>
          <div className="settings-fields">
            <label className="field">
              <span>Customer name</span>
              <input {...form.register("name")} aria-invalid={Boolean(form.formState.errors.name)} />
              {form.formState.errors.name && <small className="field-error">{form.formState.errors.name.message}</small>}
            </label>
            <div className="settings-field-row">
              <label className="field">
                <span>Customer type</span>
                <select {...form.register("customer_type")}>
                  <option value="retail">Retail</option>
                  <option value="wholesale">Wholesale</option>
                  <option value="both">Retail and wholesale</option>
                </select>
              </label>
              <label className="field">
                <span>Phone</span>
                <input {...form.register("phone")} />
              </label>
            </div>
            <div className="settings-field-row">
              <label className="field"><span>WhatsApp number</span><input {...form.register("whatsapp")} /></label>
              <label className="field">
                <span>Email</span>
                <input type="email" {...form.register("email")} aria-invalid={Boolean(form.formState.errors.email)} />
                {form.formState.errors.email && <small className="field-error">{form.formState.errors.email.message}</small>}
              </label>
            </div>
            <label className="field"><span>Address</span><input {...form.register("address")} /></label>
            {canRecordOpeningBalance && !editingCustomer && (
              <>
                <div className="settings-field-row">
                  <label className="field">
                    <span>Opening amount owed to MJD Square (NGN)</span>
                    <input inputMode="decimal" {...form.register("opening_balance")} />
                    {form.formState.errors.opening_balance && <small className="field-error">{form.formState.errors.opening_balance.message}</small>}
                  </label>
                  <label className="field">
                    <span>Effective date</span>
                    <input type="date" {...form.register("opening_balance_date")} />
                    {form.formState.errors.opening_balance_date && <small className="field-error">{form.formState.errors.opening_balance_date.message}</small>}
                  </label>
                </div>
                <label className="field">
                  <span>Opening balance source notes</span>
                  <input placeholder="For example, balance from handwritten ledger" {...form.register("opening_balance_notes")} />
                  {form.formState.errors.opening_balance_notes && <small className="field-error">{form.formState.errors.opening_balance_notes.message}</small>}
                </label>
              </>
            )}
            <label className="field"><span>Notes</span><input {...form.register("notes")} /></label>
          </div>
          {actionError && <p className="form-alert" role="alert">{actionError}</p>}
          <div className="settings-card-footer">
            <span className="settings-hint">Customer records are retained; deactivate instead of deleting.</span>
            <div className="record-form-actions">
              {editingCustomer && <button className="button button-secondary" onClick={() => { setEditingCustomer(null); form.reset(); }} type="button">Cancel</button>}
              <button className="button button-primary" disabled={createMutation.isPending || updateMutation.isPending} type="submit">
                {createMutation.isPending || updateMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <UserRoundPlus size={16} />}
                {editingCustomer ? "Save customer" : "Add customer"}
              </button>
            </div>
          </div>
        </form>

        <section className="settings-card record-list-card">
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><Users size={18} /></span>
            <div><h2>Customer directory</h2><p>Opening balances are documented migration entries, not historical invoices.</p></div>
          </div>
          {customersQuery.isPending ? (
            <div className="loading-panel"><LoaderCircle className="spin" size={19} /> Loading customers…</div>
          ) : customersQuery.isError ? (
            <p className="form-alert" role="alert">
              {customersQuery.error instanceof ApiError ? customersQuery.error.message : "Unable to load customers."}
            </p>
          ) : customersQuery.data.length === 0 ? (
            <p className="empty-staff">No customer records yet.</p>
          ) : (
            <div className="record-list">
              {customersQuery.data.map((customer) => (
                <article className="record-row" key={customer.id}>
                  <span className="profile-avatar">{customer.name.slice(0, 1).toUpperCase()}</span>
                  <div className="record-details">
                    <strong>{customer.name}</strong>
                    <small>{customer.phone || customer.email || "No contact details"} · {customer.customer_type}</small>
                    {customer.opening_balances.map((balance) => (
                      <small className="record-note" key={`${balance.effective_date}-${balance.source_notes}`}>
                        Opening balance {formatNaira(balance.amount)} from {balance.effective_date}
                      </small>
                    ))}
                  </div>
                  <strong className="record-amount">{formatNaira(customer.opening_balance_total)}</strong>
                  <span className={`staff-status${customer.is_active ? " staff-status-active" : ""}`}>
                    {customer.is_active ? "Active" : "Inactive"}
                  </span>
                  <button
                    className="button button-secondary record-action"
                    onClick={() => editCustomer(customer)}
                    type="button"
                  >
                    Edit
                  </button>
                  <button
                    className="button button-secondary record-action"
                    disabled={statusMutation.isPending}
                    onClick={() => statusMutation.mutate({ id: customer.id, is_active: !customer.is_active })}
                    type="button"
                  >
                    {customer.is_active ? "Deactivate" : "Reactivate"}
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
