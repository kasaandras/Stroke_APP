"use client";
import type { FieldSpec } from "@/lib/fields";

type Props = {
  field: FieldSpec;
  value: number | undefined;
  onChange: (v: number | undefined) => void;
  warning?: string;
};

export default function NumberInput({ field, value, onChange, warning }: Props) {
  return (
    <label className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-slate-700">{field.label}</span>
        <span className="text-[11px] tabular-nums text-slate-400">
          {field.min}–{field.max}
          {field.hint ? ` · ${field.hint}` : ""}
        </span>
      </div>
      <input
        type="number"
        inputMode="decimal"
        min={field.min}
        max={field.max}
        step={field.step ?? 1}
        value={value ?? ""}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") {
            onChange(undefined);
            return;
          }
          const n = Number(raw);
          if (Number.isNaN(n)) return;
          onChange(n);
        }}
        className="w-full rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm tabular-nums text-slate-900 transition focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-100"
      />
      {warning ? (
        <span className="text-[11px] text-amber-700">{warning}</span>
      ) : null}
    </label>
  );
}
