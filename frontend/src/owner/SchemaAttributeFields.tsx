import { useId, useMemo } from "react";

import type { EntitySchema, EntitySchemaField } from "./api";

const SUPPORTED_FIELD_TYPES = new Set<EntitySchemaField["type"]>([
  "string",
  "integer",
  "number",
  "boolean",
  "enum",
  "string_list",
]);
const SAFE_FIELD_KEY = /^[a-z][a-z0-9_]{0,63}$/;

function safeFields(schema: EntitySchema | null | undefined) {
  return (schema?.fields || []).filter((field) =>
    SAFE_FIELD_KEY.test(field.key) && SUPPORTED_FIELD_TYPES.has(field.type));
}

function listValue(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string").join("\n")
    : "";
}

function inputValue(value: unknown) {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function nextNumericValue(raw: string, integer: boolean) {
  if (!raw) return undefined;
  const parsed = integer ? Number.parseInt(raw, 10) : Number(raw);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export default function SchemaAttributeFields({
  schema,
  values,
  onChange,
  variant = "owner",
}: {
  schema: EntitySchema | null | undefined;
  values: Record<string, unknown>;
  onChange: (values: Record<string, unknown>) => void;
  variant?: "owner" | "admin";
}) {
  const idPrefix = useId().replace(/:/g, "");
  const fields = useMemo(() => safeFields(schema), [schema]);
  const sections = useMemo(() => {
    const fieldsByKey = new Map(fields.map((field) => [field.key, field]));
    const seen = new Set<string>();
    const ordered = (schema?.sections || []).flatMap((section) => {
      const sectionFields = section.fields.flatMap((key) => {
        const field = fieldsByKey.get(key);
        if (!field || seen.has(key)) return [];
        seen.add(key);
        return [field];
      });
      return sectionFields.length ? [{ key: section.key, title: section.title, fields: sectionFields }] : [];
    });
    const remaining = fields.filter((field) => !seen.has(field.key));
    return remaining.length
      ? [...ordered, { key: "details", title: "Дополнительные характеристики", fields: remaining }]
      : ordered;
  }, [fields, schema?.sections]);

  function update(key: string, value: unknown) {
    const next = { ...values };
    if (value === undefined || value === "" || (Array.isArray(value) && !value.length)) {
      delete next[key];
    } else {
      next[key] = value;
    }
    onChange(next);
  }

  if (!fields.length) {
    return (
      <p className={variant === "admin" ? "text-sm text-muted-foreground" : "owner-empty"}>
        Для выбранного типа нет дополнительных полей.
      </p>
    );
  }

  return (
    <div className={variant === "admin" ? "space-y-5" : "owner-schema-sections"}>
      {sections.map((section) => (
        <fieldset
          key={section.key}
          className={variant === "admin"
            ? "rounded-2xl border border-border bg-background/55 p-4"
            : "owner-schema-section"}
        >
          <legend className={variant === "admin" ? "px-2 text-sm font-semibold text-foreground" : undefined}>
            {section.title}
          </legend>
          <div className={variant === "admin" ? "mt-2 grid gap-4 md:grid-cols-2" : "owner-schema-grid"}>
            {section.fields.map((field) => {
              const id = `${idPrefix}-${field.key}`;
              const label = `${field.label}${field.unit ? `, ${field.unit}` : ""}`;
              if (field.type === "boolean") {
                return (
                  <label
                    key={field.key}
                    htmlFor={id}
                    className={variant === "admin"
                      ? "flex items-center gap-3 rounded-xl border border-border bg-card/70 px-4 py-3 text-sm text-foreground"
                      : "owner-schema-checkbox"}
                  >
                    <input
                      id={id}
                      type="checkbox"
                      checked={values[field.key] === true}
                      onChange={(event) => update(field.key, event.target.checked)}
                    />
                    <span>{field.label}{field.required ? " *" : ""}</span>
                  </label>
                );
              }
              if (field.type === "enum") {
                return (
                  <label key={field.key} htmlFor={id}>
                    {label}{field.required ? " *" : ""}
                    <select
                      id={id}
                      className={variant === "admin" ? "admin-input" : undefined}
                      required={field.required}
                      value={inputValue(values[field.key])}
                      onChange={(event) => {
                        const selected = field.options?.find((option) => String(option) === event.target.value);
                        update(field.key, selected);
                      }}
                    >
                      <option value="">Не выбрано</option>
                      {(field.options || []).map((option) => (
                        <option key={String(option)} value={String(option)}>{String(option)}</option>
                      ))}
                    </select>
                  </label>
                );
              }
              if (field.type === "string_list") {
                return (
                  <label key={field.key} htmlFor={id}>
                    {label}{field.required ? " *" : ""}
                    <textarea
                      id={id}
                      rows={3}
                      className={variant === "admin" ? "admin-input resize-y" : undefined}
                      required={field.required}
                      value={listValue(values[field.key])}
                      placeholder="По одному значению в строке"
                      onChange={(event) => update(
                        field.key,
                        event.target.value
                          .split(/[\n,]+/)
                          .map((item) => item.trim())
                          .filter(Boolean)
                          .slice(0, field.max_items || 50),
                      )}
                    />
                  </label>
                );
              }
              const numeric = field.type === "integer" || field.type === "number";
              return (
                <label key={field.key} htmlFor={id}>
                  {label}{field.required ? " *" : ""}
                  <input
                    id={id}
                    className={variant === "admin" ? "admin-input" : undefined}
                    type={numeric ? "number" : "text"}
                    step={field.type === "number" ? "any" : undefined}
                    min={field.min}
                    max={field.max}
                    maxLength={numeric ? undefined : field.max_length}
                    required={field.required}
                    value={inputValue(values[field.key])}
                    onChange={(event) => update(
                      field.key,
                      numeric
                        ? nextNumericValue(event.target.value, field.type === "integer")
                        : event.target.value,
                    )}
                  />
                </label>
              );
            })}
          </div>
        </fieldset>
      ))}
    </div>
  );
}
