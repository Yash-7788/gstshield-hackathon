import { useState } from "react";

type Item = {
  description: string;
  sku: string;
  unit: string;
  quantity: string;
  taxable_value: string;
};
const fields: Array<[keyof Item, string]> = [
  ["description", "Item name"],
  ["sku", "Item code, if available"],
  ["unit", "Unit, such as pieces"],
  ["quantity", "Quantity"],
  ["taxable_value", "Goods value"],
];
export function itemsFrom(
  data: Record<string, FormDataEntryValue>,
  prefix = "items",
): Item[] {
  const count = Number(data[prefix + "_count"] || 0);
  return Array.from(
    { length: count },
    (_, index) =>
      Object.fromEntries(
        fields.map(([key]) => [
          key,
          String(data[`${prefix}_${index}_${key}`] || ""),
        ]),
      ) as Item,
  );
}
export default function InvoiceItems({
  value,
  prefix = "items",
}: {
  value?: unknown;
  prefix?: string;
}) {
  const [rows, setRows] = useState(() =>
    (Array.isArray(value) ? value : []).map((item) => ({
      id: crypto.randomUUID(),
      fields: Object.fromEntries(
        fields.map(([key]) => [key, String(item?.[key] ?? "")]),
      ) as Item,
    })),
  );
  return (
    <fieldset className="invoice-items">
      <legend>Individual items</legend>
      <p>
        Add the items printed on this record. Item values should add up to the
        goods value above.
      </p>
      <input type="hidden" name={prefix + "_count"} value={rows.length} />
      {rows.map((row, index) => (
        <div className="item-row" key={row.id}>
          <strong>Item {index + 1}</strong>
          {fields.map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                name={`${prefix}_${index}_${key}`}
                value={row.fields[key]}
                required={key !== "sku"}
                maxLength={
                  key === "description" ? 200 : key === "sku" ? 64 : 24
                }
                onChange={(event) =>
                  setRows((current) =>
                    current.map((item) =>
                      item.id === row.id
                        ? {
                            ...item,
                            fields: {
                              ...item.fields,
                              [key]: event.target.value,
                            },
                          }
                        : item,
                    ),
                  )
                }
              />
            </label>
          ))}
          <button
            type="button"
            onClick={() =>
              setRows((current) => current.filter((item) => item.id !== row.id))
            }
          >
            Remove item {index + 1}
          </button>
        </div>
      ))}
      <button
        type="button"
        disabled={rows.length >= 100}
        onClick={() =>
          setRows((current) => [
            ...current,
            {
              id: crypto.randomUUID(),
              fields: {
                description: "",
                sku: "",
                unit: "",
                quantity: "",
                taxable_value: "",
              },
            },
          ])
        }
      >
        Add item
      </button>
      {!rows.length && (
        <p>
          No item details recorded. Order and delivery matches will need review.
        </p>
      )}
    </fieldset>
  );
}
