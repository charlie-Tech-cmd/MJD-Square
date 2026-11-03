import { zodResolver } from "@hookform/resolvers/zod";
import { Check, LoaderCircle, Save, Settings2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";

const businessSettingsSchema = z.object({
  business_name: z.string().trim().min(1, "Business name is required.").max(160),
  currency: z.string().regex(/^[A-Z]{3}$/, "Use a 3-letter currency code, such as NGN."),
  timezone: z.string().trim().min(1, "Timezone is required.").max(64),
  payment_methods: z.string().trim().min(1, "Add at least one payment method."),
});

type BusinessSettingsValues = z.infer<typeof businessSettingsSchema>;

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [saveError, setSaveError] = useState("");
  const settingsQuery = useQuery({ queryKey: ["business-settings"], queryFn: api.getSettings });
  const form = useForm<BusinessSettingsValues>({ resolver: zodResolver(businessSettingsSchema) });

  useEffect(() => {
    if (settingsQuery.data) {
      form.reset({
        ...settingsQuery.data,
        payment_methods: settingsQuery.data.payment_methods.join(", "),
      });
    }
  }, [form, settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: api.updateSettings,
    onSuccess: async (settings) => {
      setSaveError("");
      await queryClient.setQueryData(["business-settings"], settings);
      form.reset({ ...settings, payment_methods: settings.payment_methods.join(", ") });
    },
    onError: (error) => {
      setSaveError(error instanceof ApiError ? error.message : "Unable to save settings.");
    },
  });

  const submit = form.handleSubmit((values) => {
    const paymentMethods = values.payment_methods.split(",").map((method) => method.trim());
    if (paymentMethods.some((method) => !method) || new Set(paymentMethods.map((method) => method.toLowerCase())).size !== paymentMethods.length) {
      setSaveError("Enter distinct payment methods separated by commas.");
      return;
    }
    saveMutation.mutate({
      business_name: values.business_name,
      currency: values.currency,
      timezone: values.timezone,
      payment_methods: paymentMethods,
    });
  });

  if (settingsQuery.isPending) {
    return <div className="loading-panel"><LoaderCircle className="spin" size={20} /> Loading business settings…</div>;
  }
  if (settingsQuery.isError) {
    return (
      <div className="form-alert" role="alert">
        {settingsQuery.error instanceof ApiError
          ? settingsQuery.error.message
          : "Unable to load business settings. Please try again."}
      </div>
    );
  }

  return (
    <div className="settings-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">WORKSPACE CONFIGURATION</span>
          <h1>Business settings</h1>
          <p>Keep the details used across invoices, receipts, and business reports accurate.</p>
        </div>
      </div>
      <form className="settings-card" onSubmit={submit}>
        <div className="settings-card-heading">
          <span className="settings-heading-icon"><Settings2 size={18} /></span>
          <div>
            <h2>Business profile</h2>
            <p>These are the default details for your MJD Square workspace.</p>
          </div>
        </div>
        <div className="settings-fields">
          <label className="field">
            <span>Business name</span>
            <input {...form.register("business_name")} aria-invalid={Boolean(form.formState.errors.business_name)} />
            {form.formState.errors.business_name && <small className="field-error">{form.formState.errors.business_name.message}</small>}
          </label>
          <div className="settings-field-row">
            <label className="field">
              <span>Currency</span>
              <input {...form.register("currency")} aria-invalid={Boolean(form.formState.errors.currency)} maxLength={3} />
              {form.formState.errors.currency && <small className="field-error">{form.formState.errors.currency.message}</small>}
            </label>
            <label className="field">
              <span>Time zone</span>
              <input {...form.register("timezone")} aria-invalid={Boolean(form.formState.errors.timezone)} />
              {form.formState.errors.timezone && <small className="field-error">{form.formState.errors.timezone.message}</small>}
            </label>
          </div>
          <label className="field">
            <span>Manual payment methods</span>
            <input
              {...form.register("payment_methods")}
              aria-invalid={Boolean(form.formState.errors.payment_methods)}
              placeholder="Cash, POS, Bank transfer"
            />
            <small className="field-help">Separate methods with commas. These are manual channels, not a payment gateway.</small>
            {form.formState.errors.payment_methods && <small className="field-error">{form.formState.errors.payment_methods.message}</small>}
          </label>
        </div>
        {saveError && <p className="form-alert" role="alert">{saveError}</p>}
        <div className="settings-card-footer">
          <span className="settings-hint"><Check size={15} /> Saved changes are recorded in the audit history.</span>
          <button className="button button-primary" disabled={saveMutation.isPending || !form.formState.isDirty} type="submit">
            {saveMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Save size={16} />}
            Save changes
          </button>
        </div>
      </form>
    </div>
  );
}
