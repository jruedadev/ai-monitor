import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import {
  fetchHistory,
  fetchRoiSettings,
  saveRoiSettings,
  type DailyProjectRow,
  type RoiSettings,
  type UsageSnapshot,
} from "@/lib/api";
import { collectSessions, sessionDurationSeconds } from "@/lib/sessions";
import { SOURCE_META } from "@/lib/sources";
import { clientOf, groupProjectsByClient } from "@/lib/clients";

interface RoiViewProps {
  sources: UsageSnapshot["sources"] | null;
}

const ROI_SOURCES = ["claude_code", "codex"] as const;
type RoiSource = (typeof ROI_SOURCES)[number];

const SUBSCRIPTION_KEY: Record<RoiSource, "subscription_cost_claude" | "subscription_cost_codex"> = {
  claude_code: "subscription_cost_claude",
  codex: "subscription_cost_codex",
};

const SUBSCRIPTION_START_KEY: Record<RoiSource, "subscription_start_claude" | "subscription_start_codex"> = {
  claude_code: "subscription_start_claude",
  codex: "subscription_start_codex",
};

function formatUsd(value: number) {
  return `$${value.toFixed(2)}`;
}

function monthKey(date: string): string {
  return date.slice(0, 7);
}

function monthLabel(key: string): string {
  const [year, month] = key.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("es-ES", { year: "numeric", month: "long" });
}

/** Genera las claves YYYY-MM desde `start` (inclusive) hasta hoy (inclusive). */
function monthRange(start: string): string[] {
  const startKey = monthKey(start);
  const [startYear, startMonth] = startKey.split("-").map(Number);
  const now = new Date();
  const endYear = now.getFullYear();
  const endMonth = now.getMonth() + 1;

  const keys: string[] = [];
  let year = startYear;
  let month = startMonth;
  while (year < endYear || (year === endYear && month <= endMonth)) {
    keys.push(`${year}-${String(month).padStart(2, "0")}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return keys;
}

export function RoiView({ sources }: RoiViewProps) {
  const [settings, setSettings] = useState<RoiSettings | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [scopeFilter, setScopeFilter] = useState<string>("");
  const [historyRows, setHistoryRows] = useState<DailyProjectRow[]>([]);

  useEffect(() => {
    fetchRoiSettings().then((s) => {
      setSettings(s);
      setDraft({
        subscription_cost_claude: s.subscription_cost_claude?.toString() ?? "",
        subscription_cost_codex: s.subscription_cost_codex?.toString() ?? "",
        hourly_rate: s.hourly_rate?.toString() ?? "",
        subscription_start_claude: s.subscription_start_claude ?? "",
        subscription_start_codex: s.subscription_start_codex ?? "",
      });
    });
  }, []);

  const earliestStart = [settings?.subscription_start_claude, settings?.subscription_start_codex]
    .filter((d): d is string => Boolean(d))
    .sort()[0];

  useEffect(() => {
    if (!earliestStart) {
      setHistoryRows([]);
      return;
    }
    const days = Math.ceil((Date.now() - new Date(earliestStart).getTime()) / 86_400_000) + 1;
    fetchHistory(Math.max(days, 1))
      .then((data) => setHistoryRows(data.daily_project))
      .catch((err) => console.error("Error al cargar /api/history para ROI:", err));
  }, [earliestStart]);

  const handleSave = async () => {
    setSaving(true);
    const payload: Partial<RoiSettings> = {
      subscription_cost_claude: draft.subscription_cost_claude ? Number(draft.subscription_cost_claude) : null,
      subscription_cost_codex: draft.subscription_cost_codex ? Number(draft.subscription_cost_codex) : null,
      hourly_rate: draft.hourly_rate ? Number(draft.hourly_rate) : null,
      subscription_start_claude: draft.subscription_start_claude || null,
      subscription_start_codex: draft.subscription_start_codex || null,
    };
    const updated = await saveRoiSettings(payload);
    setSettings(updated);
    setSaving(false);
  };

  if (!settings) return null;

  const allProjectPaths = Array.from(
    new Set(ROI_SOURCES.flatMap((source) => Object.keys(sources?.[source] ?? {}))),
  );
  const projectsByClient = groupProjectsByClient(allProjectPaths);
  const clientOptions = Object.keys(projectsByClient).sort();

  const matchesScope = (path: string): boolean => {
    if (!scopeFilter) return true;
    if (scopeFilter.startsWith("client:")) return clientOf(path) === scopeFilter.slice(7);
    if (scopeFilter.startsWith("project:")) return path === scopeFilter.slice(8);
    return true;
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-card p-5 space-y-4">
        <h2 className="text-sm font-medium">Parametrización</h2>
        <label className="block space-y-1.5">
          <span className="text-xs text-muted-foreground">Acotar a</span>
          <select
            className="w-full max-w-xs rounded-lg border bg-background px-3 py-2 text-sm"
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value)}
          >
            <option value="">Todos los proyectos</option>
            {clientOptions.map((client) => (
              <optgroup key={client} label={client}>
                <option value={`client:${client}`}>Todo {client}</option>
                {projectsByClient[client].map((path) => (
                  <option key={path} value={`project:${path}`}>
                    {path.split("/").filter(Boolean).pop() ?? path}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Field
            label="Suscripción Claude ($/mes)"
            value={draft.subscription_cost_claude}
            onChange={(v) => setDraft((d) => ({ ...d, subscription_cost_claude: v }))}
          />
          <Field
            label="Suscripción Codex ($/mes)"
            value={draft.subscription_cost_codex}
            onChange={(v) => setDraft((d) => ({ ...d, subscription_cost_codex: v }))}
          />
          <Field
            label="Tarifa por hora ($)"
            value={draft.hourly_rate}
            onChange={(v) => setDraft((d) => ({ ...d, hourly_rate: v }))}
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <DateField
            label="Inicio suscripción Claude"
            value={draft.subscription_start_claude}
            onChange={(v) => setDraft((d) => ({ ...d, subscription_start_claude: v }))}
          />
          <DateField
            label="Inicio suscripción Codex"
            value={draft.subscription_start_codex}
            onChange={(v) => setDraft((d) => ({ ...d, subscription_start_codex: v }))}
          />
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          <Save className="h-4 w-4" />
          {saving ? "Guardando..." : "Guardar"}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {ROI_SOURCES.map((source) => (
          <SourceRoiCard
            key={source}
            source={source}
            sources={sources}
            settings={settings}
            matchesScope={matchesScope}
            historyRows={historyRows}
          />
        ))}
      </div>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="space-y-1.5 block">
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        type="number"
        min="0"
        step="0.01"
        placeholder="—"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
      />
    </label>
  );
}

function DateField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="space-y-1.5 block">
      <span className="text-xs text-muted-foreground">{label}</span>
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
      />
    </label>
  );
}

function SourceRoiCard({
  source,
  sources,
  settings,
  matchesScope,
  historyRows,
}: {
  source: RoiSource;
  sources: UsageSnapshot["sources"] | null;
  settings: RoiSettings;
  matchesScope: (path: string) => boolean;
  historyRows: DailyProjectRow[];
}) {
  const meta = SOURCE_META[source];
  const projects = sources?.[source] ?? {};
  const apiCost = Object.entries(projects)
    .filter(([path]) => matchesScope(path))
    .reduce((sum, [, p]) => sum + p.cost, 0);
  const subscriptionCost = settings[SUBSCRIPTION_KEY[source]];
  const subscriptionStart = settings[SUBSCRIPTION_START_KEY[source]];

  const sessions = collectSessions(sources, source).filter((s) => matchesScope(s.project));
  const totalHours = sessions.reduce((sum, s) => sum + sessionDurationSeconds(s), 0) / 3600;
  const hourlyRate = settings.hourly_rate;
  const valueGenerated = hourlyRate !== null ? totalHours * hourlyRate : null;

  const monthly = subscriptionStart
    ? monthRange(subscriptionStart).map((key) => {
        const apiCostMonth = historyRows
          .filter((row) => row.source === source && monthKey(row.date) === key && matchesScope(row.project))
          .reduce((sum, row) => sum + (row.cost ?? 0), 0);
        return { key, apiCostMonth };
      })
    : [];

  const apiCostScoped = subscriptionStart
    ? monthly.reduce((sum, m) => sum + m.apiCostMonth, 0)
    : apiCost;
  const subscriptionTotalCost =
    subscriptionStart && subscriptionCost !== null ? subscriptionCost * monthly.length : subscriptionCost;

  return (
    <div className="rounded-xl border bg-card p-5 space-y-3">
      <div className="flex items-center gap-2">
        <meta.icon className="h-4 w-4" style={{ color: meta.color }} />
        <h3 className="text-sm font-medium">{meta.label}</h3>
      </div>

      <Row
        label={subscriptionStart ? `Costo real (API) desde ${subscriptionStart}` : "Costo real (API)"}
        value={formatUsd(apiCostScoped)}
      />
      <Row
        label={
          subscriptionStart
            ? `Costo suscripción (${monthly.length} ${monthly.length === 1 ? "mes" : "meses"})`
            : "Costo suscripción"
        }
        value={subscriptionTotalCost !== null ? formatUsd(subscriptionTotalCost) : "—"}
      />
      {subscriptionTotalCost !== null && (
        <Row
          label={apiCostScoped <= subscriptionTotalCost ? "Ahorro vs. suscripción" : "Sobrecosto vs. suscripción"}
          value={formatUsd(Math.abs(subscriptionTotalCost - apiCostScoped))}
          emphasize
        />
      )}

      <div className="h-px bg-border my-1" />

      <Row label="Horas de sesión" value={totalHours.toFixed(1)} />
      <Row
        label="Valor generado"
        value={valueGenerated !== null ? formatUsd(valueGenerated) : "—"}
      />
      {valueGenerated !== null && (
        <Row
          label="ROI (valor / costo API)"
          value={apiCost > 0 ? `${(valueGenerated / apiCost).toFixed(1)}x` : "—"}
          emphasize
        />
      )}

      {monthly.length > 0 && (
        <>
          <div className="h-px bg-border my-1" />
          <div className="space-y-1.5">
            <span className="text-xs text-muted-foreground">Desglose mensual desde {subscriptionStart}</span>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground text-left">
                  <th className="font-normal py-1">Mes</th>
                  <th className="font-normal py-1 text-right">Costo API</th>
                  <th className="font-normal py-1 text-right">Suscripción</th>
                  <th className="font-normal py-1 text-right">Diferencia</th>
                </tr>
              </thead>
              <tbody>
                {monthly.map(({ key, apiCostMonth }) => (
                  <tr key={key} className="tabular-nums">
                    <td className="py-0.5 capitalize">{monthLabel(key)}</td>
                    <td className="py-0.5 text-right">{formatUsd(apiCostMonth)}</td>
                    <td className="py-0.5 text-right">
                      {subscriptionCost !== null ? formatUsd(subscriptionCost) : "—"}
                    </td>
                    <td className="py-0.5 text-right">
                      {subscriptionCost !== null
                        ? formatUsd(Math.abs(subscriptionCost - apiCostMonth))
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Row({ label, value, emphasize }: { label: string; value: string; emphasize?: boolean }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={emphasize ? "font-semibold tabular-nums" : "tabular-nums"}>{value}</span>
    </div>
  );
}
