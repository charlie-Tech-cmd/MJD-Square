import { zodResolver } from "@hookform/resolvers/zod";
import { CircleDollarSign, LoaderCircle, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { formatNaira } from "../lib/format";
import type { User } from "../types";

const todayInBusinessTimezone = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Lagos" }).format(new Date());

const expenseSchema = z.object({
  category: z.string().trim().min(1, "Enter an expense category.").max(80),
  description: z.string().trim().min(1, "Describe the expense.").max(300),
  amount: z.string().regex(/^\d{1,12}(?:\.\d{1,2})?$/, "Enter an amount with up to 2 decimals."),
  expense_date: z.string().min(1, "Choose the expense date."),
  method: z.string().min(1, "Choose the payment method."),
  reference: z.string().max(100),
  notes: z.string().max(500),
});

type ExpenseValues = z.infer<typeof expenseSchema>;

interface ExpensesPageProps {
  user: User;
}

export function ExpensesPage({ user }: ExpensesPageProps) {
  const queryClient = useQueryClient();
  const expensesQuery = useQuery({ queryKey: ["expenses"], queryFn: api.expenses });
  const settingsQuery = useQuery({ queryKey: ["business-settings"], queryFn: api.getSettings });
  const form = useForm<ExpenseValues>({
    resolver: zodResolver(expenseSchema),
    defaultValues: {
      category: "",
      description: "",
      amount: "",
      expense_date: todayInBusinessTimezone(),
      method: "",
      reference: "",
      notes: "",
    },
  });
  const [formError, setFormError] = useState("");
  const createMutation = useMutation({
    mutationFn: api.createExpense,
    onSuccess: async () => {
      setFormError("");
      form.reset({
        category: "",
        description: "",
        amount: "",
        expense_date: todayInBusinessTimezone(),
        method: "",
        reference: "",
        notes: "",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["expenses"] }),
        queryClient.invalidateQueries({ queryKey: ["reports"] }),
      ]);
    },
    onError: (error) => setFormError(error instanceof ApiError ? error.message : "Unable to record expense."),
  });

  const submit = form.handleSubmit((values) => createMutation.mutate({
    category: values.category,
    description: values.description,
    amount: values.amount,
    expense_date: values.expense_date,
    method: values.method,
    reference: values.reference.trim() || null,
    notes: values.notes.trim(),
  }));
  const canCreate = user.role.permissions.some((permission) => permission.id === "expenses:create");

  if (expensesQuery.isPending || settingsQuery.isPending) {
    return <div className="loading-panel"><LoaderCircle className="spin" size={20} /> Loading expenses…</div>;
  }
  if (expensesQuery.isError || settingsQuery.isError) {
    const error = expensesQuery.error ?? settingsQuery.error;
    return <p className="form-alert" role="alert">{error instanceof ApiError ? error.message : "Unable to load expense data."}</p>;
  }

  return (
    <div className="settings-page records-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">DAILY OPERATIONS</span>
          <h1>Expenses</h1>
          <p>Record operating costs paid by cash, POS, or transfer.</p>
        </div>
      </div>
      {canCreate && (
        <form className="settings-card expense-form" onSubmit={submit}>
          <div className="settings-card-heading">
            <span className="settings-heading-icon"><CircleDollarSign size={18} /></span>
            <div><h2>Record an expense</h2><p>Expense entries are manual records, not bank-verified payments.</p></div>
          </div>
          <div className="settings-fields">
            <div className="settings-field-row">
              <label className="field"><span>Category</span><input {...form.register("category")} />{form.formState.errors.category && <small className="field-error">{form.formState.errors.category.message}</small>}</label>
              <label className="field"><span>Date</span><input type="date" {...form.register("expense_date")} />{form.formState.errors.expense_date && <small className="field-error">{form.formState.errors.expense_date.message}</small>}</label>
            </div>
            <label className="field"><span>Description</span><input {...form.register("description")} />{form.formState.errors.description && <small className="field-error">{form.formState.errors.description.message}</small>}</label>
            <div className="settings-field-row">
              <label className="field"><span>Amount (NGN)</span><input inputMode="decimal" {...form.register("amount")} />{form.formState.errors.amount && <small className="field-error">{form.formState.errors.amount.message}</small>}</label>
              <label className="field"><span>Payment method</span>
                <select {...form.register("method")}><option value="">Choose method</option>{(settingsQuery.data?.payment_methods ?? []).map((method) => <option key={method}>{method}</option>)}</select>
                {form.formState.errors.method && <small className="field-error">{form.formState.errors.method.message}</small>}
              </label>
            </div>
            <div className="settings-field-row">
              <label className="field"><span>Reference (optional)</span><input {...form.register("reference")} /></label>
              <label className="field"><span>Notes (optional)</span><input {...form.register("notes")} /></label>
            </div>
          </div>
          {formError && <p className="form-alert" role="alert">{formError}</p>}
          {createMutation.isSuccess && <p className="success-alert" role="status">Expense recorded.</p>}
          <div className="settings-card-footer">
            <span className="settings-hint">Expenses remain in the audit history.</span>
            <button className="button button-primary" disabled={createMutation.isPending} type="submit">
              {createMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />} Record expense
            </button>
          </div>
        </form>
      )}
      <section className="settings-card record-list-card transaction-history-card">
        <div className="settings-card-heading">
          <span className="settings-heading-icon"><CircleDollarSign size={18} /></span>
          <div><h2>Recent expenses</h2><p>Expenses recorded manually by your team.</p></div>
        </div>
        {expensesQuery.data.length === 0 ? <p className="empty-staff">No expenses recorded yet.</p> : (
          <div className="record-list">
            {expensesQuery.data.map((expense) => (
              <article className="record-row" key={expense.id}>
                <div className="record-details">
                  <strong>{expense.description}</strong>
                  <small>{expense.expense_date} · {expense.category} · {expense.method}{expense.reference ? ` · ${expense.reference}` : ""}</small>
                  {expense.notes && <small>{expense.notes}</small>}
                </div>
                <strong className="record-amount">{formatNaira(expense.amount)}</strong>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
