import { zodResolver } from "@hookform/resolvers/zod";
import { Building2, LoaderCircle, Plus, Truck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { formatNaira } from "../lib/format";
import { hasPermission } from "../lib/permissions";
import type { Supplier, User } from "../types";

const supplierSchema = z.object({
  name: z.string().trim().min(1, "Enter the supplier's name.").max(160),
  contact_person: z.string().max(160),
  phone: z.string().max(40),
  email: z.union([z.email("Enter a valid email address."), z.literal("")]),
  address: z.string().max(500),
  payment_terms_days: z.union([z.literal(""), z.string().regex(/^\d{1,4}$/, "Enter days as a whole number.")]),
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

type SupplierValues = z.infer<typeof supplierSchema>;

interface SuppliersPageProps {
  user: User;
}

export function SuppliersPage({ user }: SuppliersPageProps) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const canRecordOpeningBalance = hasPermission(user, "suppliers:opening_balance");
  const suppliersQuery = useQuery({ queryKey: ["suppliers"], queryFn: api.suppliers });
  const form = useForm<SupplierValues>({
    resolver: zodResolver(supplierSchema),
    defaultValues: {
      name: "",
      contact_person: "",
      phone: "",
      email: "",
      address: "",
      payment_terms_days: "",
      notes: "",
      opening_balance: "0.00",
      opening_balance_date: "",
      opening_balance_notes: "",
    },
  });
  const createMutation = useMutation({
    mutationFn: api.createSupplier,
    onSuccess: async () => {
      setActionError("");
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Unable to create supplier.");
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: Parameters<typeof api.updateSupplier>[1] }) =>
      api.updateSupplier(id, changes),
    onSuccess: async () => {
      setActionError("");
      setEditingSupplier(null);
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Unable to update supplier.");
    },
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.updateSupplier(id, { is_active }),
    onSuccess: async () => {
      setActionError("");
      await queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
    onError: (error) => {
      setActionError(error instanceof ApiError ? error.message : "Unable to update supplier.");
    },
  });

  const submit = form.handleSubmit((values) => {
    const fields = {
      name: values.name,
      contact_person: values.contact_person.trim() || null,
      phone: values.phone.trim() || null,
      email: values.email || null,
      address: values.address.trim() || null,
      payment_terms_days: values.payment_terms_days ? Number.parseInt(values.payment_terms_days, 10) : null,
      notes: values.notes.trim(),
    };
    if (editingSupplier) {
      updateMutation.mutate({ id: editingSupplier.id, changes: fields });
    } else {
      createMutation.mutate({
        ...fields,
        opening_balance: canRecordOpeningBalance ? values.opening_balance : "0.00",
        opening_balance_date: canRecordOpeningBalance ? values.opening_balance_date || null : null,
        opening_balance_notes: canRecordOpeningBalance ? values.opening_balance_notes.trim() || null : null,
      });
    }
  });

  const editSupplier = (supplier: Supplier) => {
    setActionError("");
    setEditingSupplier(supplier);
    form.reset({
      name: supplier.name,
      contact_person: supplier.contact_person ?? "",
      phone: supplier.phone ?? "",
      email: supplier.email ?? "",
      address: supplier.address ?? "",
      payment_terms_days: supplier.payment_terms_days?.toString() ?? "",
      notes: supplier.notes,
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
          <h1>Suppliers</h1>
          <p>Track supplier contacts and documented opening amounts payable.</p>
        </div>
      </div>
      <div className="records-layout">
        <form className="settings-card record-form-card" onSubmit={submit}>
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><Building2 size={18} /></span>
            <div><h2>{editingSupplier ? "Edit supplier" : "Add supplier"}</h2><p>Supplier balances start with documented opening entries.</p></div>
          </div>
          <div className="settings-fields">
            <label className="field">
              <span>Supplier name</span>
              <input {...form.register("name")} aria-invalid={Boolean(form.formState.errors.name)} />
              {form.formState.errors.name && <small className="field-error">{form.formState.errors.name.message}</small>}
            </label>
            <div className="settings-field-row">
              <label className="field"><span>Contact person</span><input {...form.register("contact_person")} /></label>
              <label className="field"><span>Phone</span><input {...form.register("phone")} /></label>
            </div>
            <div className="settings-field-row">
              <label className="field">
                <span>Email</span>
                <input type="email" {...form.register("email")} aria-invalid={Boolean(form.formState.errors.email)} />
                {form.formState.errors.email && <small className="field-error">{form.formState.errors.email.message}</small>}
              </label>
              <label className="field">
                <span>Payment terms (days)</span>
                <input inputMode="numeric" {...form.register("payment_terms_days")} aria-invalid={Boolean(form.formState.errors.payment_terms_days)} />
                {form.formState.errors.payment_terms_days && <small className="field-error">{form.formState.errors.payment_terms_days.message}</small>}
              </label>
            </div>
            <label className="field"><span>Address</span><input {...form.register("address")} /></label>
            {canRecordOpeningBalance && !editingSupplier && (
              <>
                <div className="settings-field-row">
                  <label className="field">
                    <span>Opening amount MJD Square owes (NGN)</span>
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
                  <input placeholder="For example, statement brought forward" {...form.register("opening_balance_notes")} />
                  {form.formState.errors.opening_balance_notes && <small className="field-error">{form.formState.errors.opening_balance_notes.message}</small>}
                </label>
              </>
            )}
            <label className="field"><span>Notes</span><input {...form.register("notes")} /></label>
          </div>
          {actionError && <p className="form-alert" role="alert">{actionError}</p>}
          <div className="settings-card-footer">
            <span className="settings-hint">Supplier records are retained; deactivate instead of deleting.</span>
            <div className="record-form-actions">
              {editingSupplier && <button className="button button-secondary" onClick={() => { setEditingSupplier(null); form.reset(); }} type="button">Cancel</button>}
              <button className="button button-primary" disabled={createMutation.isPending || updateMutation.isPending} type="submit">
                {createMutation.isPending || updateMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}
                {editingSupplier ? "Save supplier" : "Add supplier"}
              </button>
            </div>
          </div>
        </form>

        <section className="settings-card record-list-card">
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><Truck size={18} /></span>
            <div><h2>Supplier directory</h2><p>Opening balances do not represent supplier invoices.</p></div>
          </div>
          {suppliersQuery.isPending ? (
            <div className="loading-panel"><LoaderCircle className="spin" size={19} /> Loading suppliers…</div>
          ) : suppliersQuery.isError ? (
            <p className="form-alert" role="alert">
              {suppliersQuery.error instanceof ApiError ? suppliersQuery.error.message : "Unable to load suppliers."}
            </p>
          ) : suppliersQuery.data.length === 0 ? (
            <p className="empty-staff">No supplier records yet.</p>
          ) : (
            <div className="record-list">
              {suppliersQuery.data.map((supplier) => (
                <article className="record-row" key={supplier.id}>
                  <span className="profile-avatar">{supplier.name.slice(0, 1).toUpperCase()}</span>
                  <div className="record-details">
                    <strong>{supplier.name}</strong>
                    <small>{supplier.phone || supplier.email || "No contact details"}{supplier.payment_terms_days !== null ? ` · ${supplier.payment_terms_days} day terms` : ""}</small>
                    {supplier.opening_balances.map((balance) => (
                      <small className="record-note" key={`${balance.effective_date}-${balance.source_notes}`}>
                        Opening payable {formatNaira(balance.amount)} from {balance.effective_date}
                      </small>
                    ))}
                  </div>
                  <strong className="record-amount">{formatNaira(supplier.opening_balance_total)}</strong>
                  <span className={`staff-status${supplier.is_active ? " staff-status-active" : ""}`}>
                    {supplier.is_active ? "Active" : "Inactive"}
                  </span>
                  <button
                    className="button button-secondary record-action"
                    onClick={() => editSupplier(supplier)}
                    type="button"
                  >
                    Edit
                  </button>
                  <button
                    className="button button-secondary record-action"
                    disabled={statusMutation.isPending}
                    onClick={() => statusMutation.mutate({ id: supplier.id, is_active: !supplier.is_active })}
                    type="button"
                  >
                    {supplier.is_active ? "Deactivate" : "Reactivate"}
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
