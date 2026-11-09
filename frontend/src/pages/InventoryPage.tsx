import { zodResolver } from "@hookform/resolvers/zod";
import { Boxes, LoaderCircle, PackagePlus, Plus, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ApiError, api } from "../lib/api";
import { formatNaira, formatQuantity } from "../lib/format";
import { hasPermission } from "../lib/permissions";
import type { Product, User } from "../types";

const moneyInput = z.string().regex(/^\d{1,12}(?:\.\d{1,2})?$/, "Use a non-negative amount with up to 2 decimals.");
const quantityInput = z.string().regex(/^\d{1,11}(?:\.\d{1,3})?$/, "Use a non-negative quantity with up to 3 decimals.");

const productSchema = z.object({
  name: z.string().trim().min(1, "Enter a product name.").max(160),
  sku: z.string().trim().min(1, "Enter a SKU or product code.").max(80),
  barcode: z.string().max(80),
  category_id: z.string(),
  description: z.string().max(5000),
  unit_id: z.string().min(1, "Choose a unit."),
  supplier_id: z.string(),
  purchase_cost: moneyInput,
  retail_price: moneyInput,
  wholesale_price: moneyInput,
  minimum_stock: quantityInput,
  opening_stock: quantityInput,
  opening_stock_reason: z.string().max(300),
  price_tiers: z.array(z.object({
    price_type: z.enum(["retail", "wholesale"]),
    minimum_quantity: quantityInput,
    unit_price: moneyInput,
  })),
}).superRefine((values, context) => {
  if (/[1-9]/.test(values.opening_stock) && !values.opening_stock_reason.trim()) {
    context.addIssue({ code: "custom", path: ["opening_stock_reason"], message: "Add the source of the opening stock." });
  }
});

type ProductValues = z.infer<typeof productSchema>;

const movementSchema = z.object({
  product_id: z.string().min(1, "Choose a product."),
  movement_type: z.enum(["adjustment", "damage"]),
  quantity_delta: z.string().regex(/^-?\d{1,11}(?:\.\d{1,3})?$/, "Enter a signed quantity with up to 3 decimals."),
  reason: z.string().trim().min(1, "Enter a reason.").max(300),
}).superRefine((values, context) => {
  if (!/[1-9]/.test(values.quantity_delta)) {
    context.addIssue({ code: "custom", path: ["quantity_delta"], message: "Movement quantity cannot be zero." });
  }
  if (values.movement_type === "damage" && !values.quantity_delta.startsWith("-")) {
    context.addIssue({ code: "custom", path: ["quantity_delta"], message: "Damaged stock must be a decrease." });
  }
});

type MovementValues = z.infer<typeof movementSchema>;

const unitSchema = z.object({
  id: z.string().regex(/^[a-z0-9][a-z0-9_-]{1,39}$/, "Use a lowercase code with letters, digits, hyphens, or underscores."),
  name: z.string().trim().min(1, "Enter a unit name.").max(80),
  abbreviation: z.string().trim().min(1, "Enter an abbreviation.").max(16),
  decimal_places: z.enum(["0", "1", "2", "3"]),
});

type UnitValues = z.infer<typeof unitSchema>;

const conversionSchema = z.object({
  from_unit_id: z.string().min(1, "Choose a source unit."),
  to_unit_id: z.string().min(1, "Choose a target unit."),
  factor: z.string().regex(/^\d{1,8}(?:\.\d{1,6})?$/, "Enter a positive factor with up to 6 decimals."),
}).refine((value) => /[1-9]/.test(value.factor), {
  path: ["factor"],
  message: "Factor must be greater than zero.",
}).refine((value) => value.from_unit_id !== value.to_unit_id, {
  path: ["to_unit_id"],
  message: "Choose two different units.",
});

type ConversionValues = z.infer<typeof conversionSchema>;

function StockHistory({ productId }: { productId: string }) {
  const [open, setOpen] = useState(false);
  const historyQuery = useQuery({
    queryKey: ["stock-movements", productId],
    queryFn: () => api.stockMovements(productId),
    enabled: open,
  });

  return (
    <details className="stock-history" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>Stock history</summary>
      {historyQuery.isPending ? (
        <small>Loading movements…</small>
      ) : historyQuery.isError ? (
        <small role="alert">Unable to load stock history.</small>
      ) : (historyQuery.data ?? []).length === 0 ? (
        <small>No stock movements recorded.</small>
      ) : (
        <ul>
          {(historyQuery.data ?? []).map((movement) => (
            <li key={movement.id}>
              <strong>{movement.quantity_delta}</strong>
              <span>{movement.movement_type.replaceAll("_", " ")} · {movement.reason}</span>
              <small>{new Date(movement.created_at).toLocaleString()}</small>
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

interface InventoryPageProps {
  user: User;
}

export function InventoryPage({ user }: InventoryPageProps) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState("");
  const [categoryError, setCategoryError] = useState("");
  const [unitError, setUnitError] = useState("");
  const [conversionError, setConversionError] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const canManage = hasPermission(user, "inventory:manage");
  const productsQuery = useQuery({ queryKey: ["products"], queryFn: api.products });
  const unitsQuery = useQuery({ queryKey: ["units"], queryFn: api.units });
  const conversionsQuery = useQuery({ queryKey: ["unit-conversions"], queryFn: api.unitConversions });
  const categoriesQuery = useQuery({ queryKey: ["product-categories"], queryFn: api.productCategories });
  const suppliersQuery = useQuery({
    queryKey: ["suppliers"],
    queryFn: api.suppliers,
    enabled: hasPermission(user, "suppliers:read"),
  });
  const productForm = useForm<ProductValues>({
    resolver: zodResolver(productSchema),
    defaultValues: {
      name: "",
      sku: "",
      barcode: "",
      category_id: "",
      description: "",
      unit_id: "piece",
      supplier_id: "",
      purchase_cost: "0.00",
      retail_price: "0.00",
      wholesale_price: "0.00",
      minimum_stock: "0",
      opening_stock: "0",
      opening_stock_reason: "",
      price_tiers: [],
    },
  });
  const tierFields = useFieldArray({ control: productForm.control, name: "price_tiers" });
  const movementForm = useForm<MovementValues>({
    resolver: zodResolver(movementSchema),
    defaultValues: { product_id: "", movement_type: "adjustment", quantity_delta: "", reason: "" },
  });
  const unitForm = useForm<UnitValues>({
    resolver: zodResolver(unitSchema),
    defaultValues: { id: "", name: "", abbreviation: "", decimal_places: "0" },
  });
  const conversionForm = useForm<ConversionValues>({
    resolver: zodResolver(conversionSchema),
    defaultValues: { from_unit_id: "", to_unit_id: "", factor: "1" },
  });

  const createMutation = useMutation({
    mutationFn: api.createProduct,
    onSuccess: async () => {
      setActionError("");
      productForm.reset();
      await queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to create product."),
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: Parameters<typeof api.updateProduct>[1] }) =>
      api.updateProduct(id, changes),
    onSuccess: async () => {
      setActionError("");
      setEditingProduct(null);
      productForm.reset();
      await queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to update product."),
  });
  const categoryMutation = useMutation({
    mutationFn: (name: string) => api.createProductCategory({ name, description: "" }),
    onSuccess: async () => {
      setCategoryError("");
      setCategoryName("");
      await queryClient.invalidateQueries({ queryKey: ["product-categories"] });
    },
    onError: (error) => setCategoryError(error instanceof ApiError ? error.message : "Unable to add category."),
  });
  const unitMutation = useMutation({
    mutationFn: (unit: Parameters<typeof api.createUnit>[0]) => api.createUnit(unit),
    onSuccess: async () => {
      setUnitError("");
      unitForm.reset();
      await queryClient.invalidateQueries({ queryKey: ["units"] });
    },
    onError: (error) => setUnitError(error instanceof ApiError ? error.message : "Unable to add unit."),
  });
  const conversionMutation = useMutation({
    mutationFn: api.createUnitConversion,
    onSuccess: async () => {
      setConversionError("");
      conversionForm.reset({ from_unit_id: "", to_unit_id: "", factor: "1" });
      await queryClient.invalidateQueries({ queryKey: ["unit-conversions"] });
    },
    onError: (error) => setConversionError(error instanceof ApiError ? error.message : "Unable to add unit conversion."),
  });
  const movementMutation = useMutation({
    mutationFn: ({ product_id, ...movement }: MovementValues) =>
      api.createStockMovement(product_id, movement),
    onSuccess: async () => {
      setActionError("");
      movementForm.reset({ product_id: "", movement_type: "adjustment", quantity_delta: "", reason: "" });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["products"] }),
        queryClient.invalidateQueries({ queryKey: ["stock-movements"] }),
      ]);
    },
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to record stock movement."),
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.updateProduct(id, { is_active }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["products"] }),
    onError: (error) => setActionError(error instanceof ApiError ? error.message : "Unable to update product."),
  });

  const submitProduct = productForm.handleSubmit((values) => {
    const changes = {
      name: values.name,
      sku: values.sku,
      barcode: values.barcode.trim() || null,
      category_id: values.category_id || null,
      description: values.description.trim(),
      unit_id: values.unit_id,
      supplier_id: values.supplier_id || null,
      purchase_cost: values.purchase_cost,
      retail_price: values.retail_price,
      wholesale_price: values.wholesale_price,
      minimum_stock: values.minimum_stock,
      price_tiers: values.price_tiers,
    };
    if (editingProduct) {
      updateMutation.mutate({ id: editingProduct.id, changes });
    } else {
      createMutation.mutate({
        ...changes,
        opening_stock: values.opening_stock,
        opening_stock_reason: values.opening_stock_reason.trim() || null,
      });
    }
  });
  const submitMovement = movementForm.handleSubmit((values) => movementMutation.mutate(values));
  const submitUnit = unitForm.handleSubmit((values) => unitMutation.mutate({
    ...values,
    decimal_places: Number.parseInt(values.decimal_places, 10),
  }));
  const submitConversion = conversionForm.handleSubmit((values) => conversionMutation.mutate(values));
  const editProduct = (product: Product) => {
    setActionError("");
    setEditingProduct(product);
    productForm.reset({
      name: product.name,
      sku: product.sku,
      barcode: product.barcode ?? "",
      category_id: product.category_id ?? "",
      description: product.description,
      unit_id: product.unit_id,
      supplier_id: product.supplier_id ?? "",
      purchase_cost: product.purchase_cost,
      retail_price: product.retail_price,
      wholesale_price: product.wholesale_price,
      minimum_stock: product.minimum_stock,
      opening_stock: "0",
      opening_stock_reason: "",
      price_tiers: product.price_tiers,
    });
  };

  const loadError = productsQuery.isError
    ? productsQuery.error
    : unitsQuery.isError
      ? unitsQuery.error
      : categoriesQuery.isError
        ? categoriesQuery.error
        : conversionsQuery.isError
          ? conversionsQuery.error
          : null;

  return (
    <div className="settings-page records-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">BUSINESS RECORDS</span>
          <h1>Products & inventory</h1>
          <p>Manage product details and record every stock change with a reason.</p>
        </div>
      </div>
      {loadError && (
        <p className="form-alert" role="alert">
          {loadError instanceof ApiError ? loadError.message : "Unable to load inventory setup data."}
        </p>
      )}
      {canManage && (
        <div className="records-layout inventory-forms">
          <form className="settings-card record-form-card" onSubmit={submitProduct}>
            <div className="settings-card-heading">
              <span className="settings-heading-icon"><PackagePlus size={18} /></span>
              <div><h2>{editingProduct ? "Edit product" : "Add product"}</h2><p>Price and quantity values are stored as exact decimals.</p></div>
            </div>
            <div className="settings-fields">
              <div className="settings-field-row">
                <label className="field">
                  <span>Product name</span>
                  <input {...productForm.register("name")} />
                  {productForm.formState.errors.name && <small className="field-error">{productForm.formState.errors.name.message}</small>}
                </label>
                <label className="field">
                  <span>SKU / product code</span>
                  <input {...productForm.register("sku")} />
                  {productForm.formState.errors.sku && <small className="field-error">{productForm.formState.errors.sku.message}</small>}
                </label>
              </div>
              <div className="settings-field-row">
                <label className="field">
                  <span>Unit of measure</span>
                  <select {...productForm.register("unit_id")}>
                    {(unitsQuery.data ?? []).map((unit) => <option key={unit.id} value={unit.id}>{unit.name} ({unit.abbreviation})</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Category</span>
                  <select {...productForm.register("category_id")}>
                    <option value="">Uncategorized</option>
                    {(categoriesQuery.data ?? []).filter((category) => category.is_active).map((category) => (
                      <option key={category.id} value={category.id}>{category.name}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="field">
                <span>Supplier (optional)</span>
                <select {...productForm.register("supplier_id")}>
                  <option value="">No supplier selected</option>
                  {(suppliersQuery.data ?? []).filter((supplier) => supplier.is_active).map((supplier) => (
                    <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
                  ))}
                </select>
              </label>
              <div className="settings-field-row">
                <label className="field"><span>Purchase cost (NGN)</span><input inputMode="decimal" {...productForm.register("purchase_cost")} /></label>
                <label className="field"><span>Retail price (NGN)</span><input inputMode="decimal" {...productForm.register("retail_price")} /></label>
              </div>
              <div className="settings-field-row">
                <label className="field"><span>Wholesale price (NGN)</span><input inputMode="decimal" {...productForm.register("wholesale_price")} /></label>
                <label className="field"><span>Low-stock threshold</span><input inputMode="decimal" {...productForm.register("minimum_stock")} /></label>
              </div>
              <label className="field"><span>Barcode (optional)</span><input {...productForm.register("barcode")} /></label>
              <label className="field"><span>Description</span><input {...productForm.register("description")} /></label>
              {!editingProduct && (
                <div className="settings-field-row">
                  <label className="field">
                    <span>Opening stock quantity</span>
                    <input inputMode="decimal" {...productForm.register("opening_stock")} />
                    {productForm.formState.errors.opening_stock && <small className="field-error">{productForm.formState.errors.opening_stock.message}</small>}
                  </label>
                  <label className="field">
                    <span>Opening stock reason</span>
                    <input {...productForm.register("opening_stock_reason")} />
                    {productForm.formState.errors.opening_stock_reason && <small className="field-error">{productForm.formState.errors.opening_stock_reason.message}</small>}
                  </label>
                </div>
              )}
              <div className="record-subsection">
                <div className="record-subsection-heading">
                  <strong>Quantity-based price tiers</strong>
                  <button className="button button-secondary" onClick={() => tierFields.append({ price_type: "wholesale", minimum_quantity: "1", unit_price: "0.00" })} type="button">
                    <Plus size={14} /> Add tier
                  </button>
                </div>
                {tierFields.fields.map((field, index) => (
                  <div className="settings-field-row tier-row" key={field.id}>
                    <label className="field">
                      <span>Price type</span>
                      <select {...productForm.register(`price_tiers.${index}.price_type`)}>
                        <option value="wholesale">Wholesale</option>
                        <option value="retail">Retail</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Minimum quantity</span>
                      <input inputMode="decimal" {...productForm.register(`price_tiers.${index}.minimum_quantity`)} />
                    </label>
                    <label className="field">
                      <span>Unit price (NGN)</span>
                      <input inputMode="decimal" {...productForm.register(`price_tiers.${index}.unit_price`)} />
                    </label>
                    <button className="button button-secondary" onClick={() => tierFields.remove(index)} type="button">Remove</button>
                  </div>
                ))}
              </div>
              <div className="category-add-row">
                <label className="field">
                  <span>New product category</span>
                  <input value={categoryName} onChange={(event) => setCategoryName(event.target.value)} />
                </label>
                <button
                  className="button button-secondary"
                  disabled={!categoryName.trim() || categoryMutation.isPending}
                  onClick={() => categoryMutation.mutate(categoryName.trim())}
                  type="button"
                >
                  {categoryMutation.isPending ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />}
                  Add category
                </button>
              </div>
              {categoryError && <p className="form-alert" role="alert">{categoryError}</p>}
            </div>
            {actionError && <p className="form-alert" role="alert">{actionError}</p>}
            <div className="settings-card-footer">
              <span className="settings-hint">Stock is changed only through recorded movements.</span>
              <div className="record-form-actions">
                {editingProduct && <button className="button button-secondary" onClick={() => { setEditingProduct(null); productForm.reset(); }} type="button">Cancel</button>}
                <button className="button button-primary" disabled={createMutation.isPending || updateMutation.isPending || unitsQuery.isPending} type="submit">
                  {createMutation.isPending || updateMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <PackagePlus size={16} />}
                  {editingProduct ? "Save product" : "Create product"}
                </button>
              </div>
            </div>
          </form>

          <form className="settings-card record-form-card" onSubmit={submitMovement}>
            <div className="settings-card-heading">
              <span className="settings-heading-icon"><SlidersHorizontal size={18} /></span>
              <div><h2>Record stock movement</h2><p>Adjustments require a reason and cannot create negative stock.</p></div>
            </div>
            <div className="settings-fields">
              <label className="field">
                <span>Product</span>
                <select {...movementForm.register("product_id")}>
                  <option value="">Choose a product</option>
                  {(productsQuery.data ?? []).map((product) => <option key={product.id} value={product.id}>{product.name} · {product.sku}</option>)}
                </select>
                {movementForm.formState.errors.product_id && <small className="field-error">{movementForm.formState.errors.product_id.message}</small>}
              </label>
              <label className="field">
                <span>Movement type</span>
                <select {...movementForm.register("movement_type")}>
                  <option value="adjustment">Stock adjustment</option>
                  <option value="damage">Damaged stock</option>
                </select>
              </label>
              <label className="field">
                <span>Quantity change (+ or −)</span>
                <input inputMode="decimal" placeholder="Positive to add, negative to remove" {...movementForm.register("quantity_delta")} />
                {movementForm.formState.errors.quantity_delta && <small className="field-error">{movementForm.formState.errors.quantity_delta.message}</small>}
              </label>
              <label className="field">
                <span>Reason</span>
                <input {...movementForm.register("reason")} />
                {movementForm.formState.errors.reason && <small className="field-error">{movementForm.formState.errors.reason.message}</small>}
              </label>
            </div>
            <div className="settings-card-footer">
              <span className="settings-hint">The API will reject a movement that makes stock negative.</span>
              <button className="button button-primary" disabled={movementMutation.isPending} type="submit">
                {movementMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}
                Record movement
              </button>
            </div>
          </form>
        </div>
      )}
      {canManage && (
        <div className="records-layout units-layout">
          <form className="settings-card record-form-card" onSubmit={submitUnit}>
            <div className="settings-card-heading">
              <span className="settings-heading-icon"><Plus size={18} /></span>
              <div><h2>Units of measure</h2><p>Choose quantity precision from zero to three decimal places.</p></div>
            </div>
            <div className="settings-fields">
              <div className="settings-field-row">
                <label className="field"><span>Unit code</span><input {...unitForm.register("id")} placeholder="bottle" />{unitForm.formState.errors.id && <small className="field-error">{unitForm.formState.errors.id.message}</small>}</label>
                <label className="field"><span>Unit name</span><input {...unitForm.register("name")} />{unitForm.formState.errors.name && <small className="field-error">{unitForm.formState.errors.name.message}</small>}</label>
              </div>
              <div className="settings-field-row">
                <label className="field"><span>Abbreviation</span><input {...unitForm.register("abbreviation")} />{unitForm.formState.errors.abbreviation && <small className="field-error">{unitForm.formState.errors.abbreviation.message}</small>}</label>
                <label className="field"><span>Decimal places</span><select {...unitForm.register("decimal_places")}><option value="0">0 (whole units)</option><option value="1">1</option><option value="2">2</option><option value="3">3</option></select></label>
              </div>
            </div>
            <div className="settings-card-footer">
              <span className="settings-hint">{(unitsQuery.data ?? []).length} units currently available.</span>
              <button className="button button-primary" disabled={unitMutation.isPending} type="submit">{unitMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}Add unit</button>
            </div>
            {unitError && <p className="form-alert" role="alert">{unitError}</p>}
          </form>
          <section className="settings-card record-form-card">
            <div className="settings-card-heading">
              <span className="settings-heading-icon"><SlidersHorizontal size={18} /></span>
              <div><h2>Unit conversions</h2><p>One source unit converts to the given number of target units.</p></div>
            </div>
            <form className="settings-fields" onSubmit={submitConversion}>
              <div className="settings-field-row">
                <label className="field"><span>From unit</span><select {...conversionForm.register("from_unit_id")}><option value="">Choose unit</option>{(unitsQuery.data ?? []).map((unit) => <option key={unit.id} value={unit.id}>{unit.name} ({unit.abbreviation})</option>)}</select>{conversionForm.formState.errors.from_unit_id && <small className="field-error">{conversionForm.formState.errors.from_unit_id.message}</small>}</label>
                <label className="field"><span>To unit</span><select {...conversionForm.register("to_unit_id")}><option value="">Choose unit</option>{(unitsQuery.data ?? []).map((unit) => <option key={unit.id} value={unit.id}>{unit.name} ({unit.abbreviation})</option>)}</select>{conversionForm.formState.errors.to_unit_id && <small className="field-error">{conversionForm.formState.errors.to_unit_id.message}</small>}</label>
              </div>
              <label className="field"><span>Target units per source unit</span><input inputMode="decimal" {...conversionForm.register("factor")} />{conversionForm.formState.errors.factor && <small className="field-error">{conversionForm.formState.errors.factor.message}</small>}</label>
              <button className="button button-primary" disabled={conversionMutation.isPending} type="submit">{conversionMutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Plus size={16} />}Add conversion</button>
            </form>
            {conversionError && <p className="form-alert" role="alert">{conversionError}</p>}
            <div className="unit-conversion-list">
              {(conversionsQuery.data ?? []).map((conversion) => {
                const from = unitsQuery.data?.find((unit) => unit.id === conversion.from_unit_id);
                const to = unitsQuery.data?.find((unit) => unit.id === conversion.to_unit_id);
                return <small key={conversion.id}>1 {from?.abbreviation ?? conversion.from_unit_id} = {conversion.factor} {to?.abbreviation ?? conversion.to_unit_id}</small>;
              })}
            </div>
          </section>
        </div>
      )}
      <section className="settings-card inventory-list-card">
        <div className="settings-card-heading">
          <span className="settings-heading-icon"><Boxes size={18} /></span>
          <div><h2>Product catalogue</h2><p>On-hand quantities reflect recorded stock movements.</p></div>
        </div>
        {productsQuery.isPending ? (
          <div className="loading-panel"><LoaderCircle className="spin" size={19} /> Loading products…</div>
        ) : productsQuery.isError ? (
          <p className="form-alert" role="alert">{productsQuery.error instanceof ApiError ? productsQuery.error.message : "Unable to load products."}</p>
        ) : productsQuery.data.length === 0 ? (
          <p className="empty-staff">No products yet.</p>
        ) : (
          <div className="record-table-wrap">
            <table className="record-table">
              <thead>
                <tr><th>Product</th><th>SKU</th><th>Category</th><th>On hand</th><th>Cost</th><th>Retail</th><th>Wholesale</th><th>Status</th>{canManage && <th>Action</th>}</tr>
              </thead>
              <tbody>
                {productsQuery.data.map((product) => (
                  <tr key={product.id}>
                    <td>
                      <strong>{product.name}</strong>
                      <small>{product.unit_name} ({product.unit_abbreviation})</small>
                      <StockHistory productId={product.id} />
                    </td>
                    <td>{product.sku}</td>
                    <td>{product.category_name || "—"}</td>
                    <td><span className={product.is_low_stock ? "stock-low" : ""}>{formatQuantity(product.stock_quantity, product.unit_decimal_places)} {product.unit_abbreviation}</span>{product.is_low_stock && <small className="stock-warning">Low stock</small>}</td>
                    <td>{formatNaira(product.purchase_cost)}</td>
                    <td>{formatNaira(product.retail_price)}</td>
                    <td>{formatNaira(product.wholesale_price)}</td>
                    <td><span className={`staff-status${product.is_active ? " staff-status-active" : ""}`}>{product.is_active ? "Active" : "Inactive"}</span></td>
                    {canManage && <td className="record-table-actions"><button className="button button-secondary record-action" onClick={() => editProduct(product)} type="button">Edit</button><button className="button button-secondary record-action" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate({ id: product.id, is_active: !product.is_active })} type="button">{product.is_active ? "Deactivate" : "Reactivate"}</button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
