/**
 * DynamicUI — client-side renderer for the dynamic-UI protocol.
 *
 * The agent emits *data only* (`docs/DYNAMIC_UI.md`): an envelope of
 * `{kind:"dynamic-ui", version:1, elements:[...]}`. This component renders
 * the element allowlist — text, buttons, card, form, progress — and fires
 * actions back to the host through `onAction`, which routes them to the
 * agent as structured intents. No JS ever executes from a payload, and
 * everything renders as plain text nodes (never innerHTML).
 *
 * Defensive by design: a malformed envelope or an unknown element type
 * renders as plain text with a small warning — this component never throws
 * on agent-supplied data.
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";

/* ---------------------------------------------------------------- types */

export type DynamicUIAction =
  | { kind: "intent"; intent: string; args?: Record<string, unknown>; confirm?: boolean }
  | { kind: "url"; url: string; confirm?: boolean };

export type DynamicUIButtonDef = {
  label: string;
  action: DynamicUIAction;
  style?: "primary" | "ghost" | "danger";
};

export type DynamicUIFieldDef = {
  name: string;
  label: string;
  field: "text" | "number" | "select" | "toggle";
  placeholder?: string;
  options?: string[];
  default?: string | number | boolean;
  min?: number;
  max?: number;
  required?: boolean;
};

export type DynamicUIElement =
  | { type: "text"; text: string; tone?: "body" | "muted" | "accent" }
  | { type: "buttons"; buttons: DynamicUIButtonDef[] }
  | { type: "card"; title: string; body?: string; actions?: DynamicUIButtonDef[] }
  | {
      type: "form";
      title?: string;
      fields: DynamicUIFieldDef[];
      submit: { label: string; action: DynamicUIAction };
    }
  | { type: "progress"; label?: string; value?: number; indeterminate?: boolean };

export type DynamicUIEnvelope = {
  kind: "dynamic-ui";
  version: 1;
  elements: DynamicUIElement[];
};

export type DynamicUIProps = {
  /** Raw payload from the agent — validated defensively at render time. */
  payload: unknown;
  /** Host wiring: fired when the user taps a button, submits a form, or opens a URL. */
  onAction: (action: DynamicUIAction) => void;
  className?: string;
};

/* ------------------------------------------------------------- validation */

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isEnvelope(payload: unknown): payload is DynamicUIEnvelope {
  if (!isRecord(payload)) return false;
  if (payload.kind !== "dynamic-ui") return false;
  if (payload.version !== 1) return false;
  return Array.isArray(payload.elements);
}

const KNOWN_TYPES = new Set(["text", "buttons", "card", "form", "progress"]);

function isHttpUrl(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

function domainOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

/* ---------------------------------------------------------------- render */

export function DynamicUI({ payload, onAction, className }: DynamicUIProps) {
  if (!isEnvelope(payload)) {
    return (
      <div className={className} role="note" aria-label="Unsupported dynamic UI">
        <UnsupportedBlock raw={payload} reason="Unrecognized dynamic-UI payload" />
      </div>
    );
  }
  return (
    <div className={`flex flex-col gap-3 ${className ?? ""}`}>
      {payload.elements.map((el, i) =>
        isRecord(el) && typeof el.type === "string" && KNOWN_TYPES.has(el.type) ? (
          <Element key={i} el={el as DynamicUIElement} onAction={onAction} />
        ) : (
          <UnsupportedBlock
            key={i}
            raw={el}
            reason={`Unsupported element type “${isRecord(el) ? String(el.type) : typeof el}”`}
          />
        ),
      )}
    </div>
  );
}

function Element({ el, onAction }: { el: DynamicUIElement; onAction: DynamicUIProps["onAction"] }) {
  switch (el.type) {
    case "text":
      return <TextEl el={el} />;
    case "buttons":
      return <ButtonsEl buttons={el.buttons ?? []} onAction={onAction} />;
    case "card":
      return <CardEl el={el} onAction={onAction} />;
    case "form":
      return <FormEl el={el} onAction={onAction} />;
    case "progress":
      return <ProgressEl el={el} />;
    default:
      return <UnsupportedBlock raw={el} reason="Unsupported element" />;
  }
}

/** Graceful fallback: unknown or malformed content renders as plain text. */
function UnsupportedBlock({ raw, reason }: { raw: unknown; reason: string }) {
  let preview: string;
  try {
    preview = JSON.stringify(raw) ?? "";
    if (preview.length > 400) preview = `${preview.slice(0, 400)}…`;
  } catch {
    preview = "[unprintable]";
  }
  return (
    <div className="rounded-md border border-border bg-elevated px-3 py-2">
      <p className="text-micro text-subtle">{reason} — showing as plain text.</p>
      {preview && <p className="mt-1 break-words text-xs text-muted">{preview}</p>}
    </div>
  );
}

function TextEl({ el }: { el: Extract<DynamicUIElement, { type: "text" }> }) {
  const tone =
    el.tone === "accent" ? "text-accent" : el.tone === "muted" ? "text-muted" : "text-fg";
  return <p className={`whitespace-pre-wrap text-sm leading-relaxed ${tone}`}>{el.text ?? ""}</p>;
}

function ButtonsEl({
  buttons,
  onAction,
}: {
  buttons: DynamicUIButtonDef[];
  onAction: DynamicUIProps["onAction"];
}) {
  if (!Array.isArray(buttons) || buttons.length === 0) {
    return <UnsupportedBlock raw={buttons} reason="Buttons element has no buttons" />;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {buttons.map((b, i) => (
        <ActionButton key={i} def={b} onAction={onAction} />
      ))}
    </div>
  );
}

/**
 * A protocol button. Destructive / confirm-flagged actions arm on first tap
 * and fire on second tap ("Tap again to confirm"). URL actions show the
 * destination domain and open in a new tab, http(s) only.
 */
function ActionButton({
  def,
  onAction,
}: {
  def: DynamicUIButtonDef;
  onAction: DynamicUIProps["onAction"];
}) {
  const [armed, setArmed] = useState(false);
  if (!isRecord(def) || typeof def.label !== "string" || !isRecord(def.action)) {
    return <UnsupportedBlock raw={def} reason="Malformed button" />;
  }
  const action = def.action as DynamicUIAction;
  const needsConfirm = action.confirm === true || def.style === "danger";

  if (action.kind === "url" && (typeof action.url !== "string" || !isHttpUrl(action.url))) {
    return (
      <UnsupportedBlock raw={def} reason="Blocked non-http(s) link — never rendered as a link" />
    );
  }

  const fire = () => {
    if (needsConfirm && !armed) {
      setArmed(true);
      window.setTimeout(() => setArmed(false), 4000);
      return;
    }
    setArmed(false);
    onAction(action);
  };

  if (action.kind === "url") {
    return (
      <button
        type="button"
        onClick={fire}
        title={action.url}
        className="inline-flex h-9 items-center gap-1.5 rounded-sm border border-border bg-transparent px-3 text-sm text-fg hover:bg-elevated"
      >
        {armed ? "Tap again to open" : def.label}
        <span className="text-micro text-subtle">{domainOf(action.url)}</span>
      </button>
    );
  }

  const variant = def.style === "ghost" ? "ghost" : def.style === "danger" ? "outline" : "primary";
  return (
    <Button
      type="button"
      size="sm"
      variant={variant}
      onClick={fire}
      className={def.style === "danger" ? "border-red-500/60 text-red-400 hover:bg-red-500/10" : ""}
    >
      {armed ? "Tap again to confirm" : def.label}
    </Button>
  );
}

function CardEl({
  el,
  onAction,
}: {
  el: Extract<DynamicUIElement, { type: "card" }>;
  onAction: DynamicUIProps["onAction"];
}) {
  return (
    <div className="rounded-lg border border-border bg-surface px-4 py-3">
      <h4 className="text-sm font-medium text-fg">{el.title ?? ""}</h4>
      {typeof el.body === "string" && el.body.length > 0 && (
        <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-muted">{el.body}</p>
      )}
      {Array.isArray(el.actions) && el.actions.length > 0 && (
        <div className="mt-3">
          <ButtonsEl buttons={el.actions} onAction={onAction} />
        </div>
      )}
    </div>
  );
}

function FormEl({
  el,
  onAction,
}: {
  el: Extract<DynamicUIElement, { type: "form" }>;
  onAction: DynamicUIProps["onAction"];
}) {
  const fields = Array.isArray(el.fields) ? el.fields : [];
  const [values, setValues] = useState<Record<string, string | number | boolean>>(() => {
    const init: Record<string, string | number | boolean> = {};
    for (const f of fields) {
      if (!isRecord(f)) continue;
      const name = f.name;
      if (typeof name !== "string") continue;
      if (f.field === "toggle") init[name] = Boolean(f.default);
      else if (f.field === "number") init[name] = typeof f.default === "number" ? f.default : "";
      else init[name] = typeof f.default === "string" ? f.default : "";
    }
    return init;
  });

  if (fields.length === 0 || !isRecord(el.submit)) {
    return <UnsupportedBlock raw={el} reason="Form element is missing fields or a submit action" />;
  }

  const set = (name: string, v: string | number | boolean) =>
    setValues((prev) => ({ ...prev, [name]: v }));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const action = el.submit.action as DynamicUIAction;
    if (action.kind === "intent") {
      onAction({
        ...action,
        args: { ...(isRecord(action.args) ? action.args : {}), ...values },
      });
    } else {
      onAction(action);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface px-4 py-3"
    >
      {typeof el.title === "string" && el.title.length > 0 && (
        <h4 className="text-sm font-medium text-fg">{el.title}</h4>
      )}
      {fields.map((f, i) => {
        if (!isRecord(f) || typeof f.name !== "string") {
          return <UnsupportedBlock key={i} raw={f} reason="Malformed form field" />;
        }
        const def = f as unknown as DynamicUIFieldDef;
        return (
          <label key={def.name} className="flex flex-col gap-1">
            <span className="text-xs text-muted">
              {def.label}
              {def.required && <span className="text-accent"> *</span>}
            </span>
            <FieldInput def={def} value={values[def.name]} onChange={(v) => set(def.name, v)} />
          </label>
        );
      })}
      <div>
        <Button type="submit" size="sm">
          {el.submit.label}
        </Button>
      </div>
    </form>
  );
}

function FieldInput({
  def,
  value,
  onChange,
}: {
  def: DynamicUIFieldDef;
  value: string | number | boolean | undefined;
  onChange: (v: string | number | boolean) => void;
}) {
  const cls =
    "h-10 rounded-md border border-border bg-elevated px-3 text-sm text-fg placeholder:text-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40";
  switch (def.field) {
    case "toggle":
      return (
        <button
          type="button"
          role="switch"
          aria-checked={value === true}
          aria-label={def.label}
          onClick={() => onChange(value !== true)}
          className={`flex h-10 items-center rounded-md border border-border bg-elevated px-3 text-sm ${
            value === true ? "text-accent" : "text-muted"
          }`}
        >
          {value === true ? "On" : "Off"}
        </button>
      );
    case "select":
      return (
        <select
          className={cls}
          value={typeof value === "string" ? value : ""}
          required={def.required}
          onChange={(e) => onChange(e.target.value)}
        >
          {(def.options ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      );
    case "number":
      return (
        <input
          type="number"
          className={cls}
          value={typeof value === "number" ? value : ""}
          min={def.min}
          max={def.max}
          required={def.required}
          onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
        />
      );
    default:
      return (
        <input
          type="text"
          className={cls}
          value={typeof value === "string" ? value : ""}
          placeholder={def.placeholder}
          required={def.required}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}

function ProgressEl({ el }: { el: Extract<DynamicUIElement, { type: "progress" }> }) {
  const indeterminate = el.indeterminate === true || typeof el.value !== "number";
  const pct = indeterminate ? 100 : Math.max(0, Math.min(1, el.value as number)) * 100;
  return (
    <div className="flex flex-col gap-1.5">
      {typeof el.label === "string" && el.label.length > 0 && (
        <span className="text-xs text-muted">{el.label}</span>
      )}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={indeterminate ? undefined : Math.round(pct)}
        aria-label={el.label ?? "Progress"}
        className="h-2 w-full overflow-hidden rounded-full bg-elevated"
      >
        <div
          className={`h-full rounded-full bg-accent ${indeterminate ? "animate-pulse" : ""}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
