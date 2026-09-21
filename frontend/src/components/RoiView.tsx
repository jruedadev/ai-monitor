import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { fetchRoiSettings, saveRoiSettings, type RoiSettings, type UsageSnapshot } from "@/lib/api";
import { collectSessions, sessionDurationSeconds } from "@/lib/sessions";
import { SOURCE_META } from "@/lib/sources";

interface RoiViewProps {
  sources: UsageSnapshot["sources"] | null;
}

const ROI_SOURCES = ["claude_code", "codex"] as const;
type RoiSource = (typeof ROI_SOURCES)[number];

const SUBSCRIPTION_KEY: Record<RoiSource, keyof RoiSettings> = {
  claude_code: "subscription_cost_claude",
  codex: "subscription_cost_codex",
};

function formatUsd(value: number) {
  return `$${value.toFixed(2)}`;
}

export function RoiView({ sources }: RoiViewProps) {
  const [settings, setSettings] = useState<RoiSettings | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchRoiSettings().then((s) => {
      setSettings(s);
      setDraft({
        subscription_cost_claude: s.subscription_cost_claude?.toString() ?? "",
        subscription_cost_codex: s.subscription_cost_codex?.toString() ?? "",
        hourly_rate: s.hourly_rate?.toString() ?? "",
      });
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const payload: Partial<RoiSettings> = {
      subscription_cost_claude: draft.subscription_cost_claude ? Number(draft.subscription_cost_claude) : null,
      subscription_cost_codex: draft.subscription_cost_codex ? Number(draft.subscription_cost_codex) : null,
      hourly_rate: draft.hourly_rate ? Number(draft.hourly_rate) : null,
    };
    const updated = await saveRoiSettings(payload);
    setSettings(updated);
    setSaving(false);
  };

  if (!settings) return null;

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-card p-5 space-y-4">
        <h2 className="text-sm font-medium">Parametrización</h2>
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
          <SourceRoiCard key={source} source={source} sources={sources} settings={settings} />
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

function SourceRoiCard({
  source,
  sources,
  settings,
}: {
  source: RoiSource;
  sources: UsageSnapshot["sources"] | null;
  settings: RoiSettings;
}) {
  const meta = SOURCE_META[source];
  const projects = sources?.[source] ?? {};
  const apiCost = Object.values(projects).reduce((sum, p) => sum + p.cost, 0);
  const subscriptionCost = settings[SUBSCRIPTION_KEY[source]];

  const sessions = collectSessions(sources, source);
  const totalHours = sessions.reduce((sum, s) => sum + sessionDurationSeconds(s), 0) / 3600;
  const hourlyRate = settings.hourly_rate;
  const valueGenerated = hourlyRate !== null ? totalHours * hourlyRate : null;

  return (
    <div className="rounded-xl border bg-card p-5 space-y-3">
      <div className="flex items-center gap-2">
        <meta.icon className="h-4 w-4" style={{ color: meta.color }} />
        <h3 className="text-sm font-medium">{meta.label}</h3>
      </div>

      <Row label="Costo real (API)" value={formatUsd(apiCost)} />
      <Row
        label="Costo suscripción"
        value={subscriptionCost !== null ? formatUsd(subscriptionCost) : "—"}
      />
      {subscriptionCost !== null && (
        <Row
          label={apiCost <= subscriptionCost ? "Ahorro vs. suscripción" : "Sobrecosto vs. suscripción"}
          value={formatUsd(Math.abs(subscriptionCost - apiCost))}
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
