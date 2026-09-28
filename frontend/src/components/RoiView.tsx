import { useEffect, useState } from "react";
import { AlertCircle, Scale } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import {
  fetchHistory,
  fetchRoiSettings,
  type DailyProjectRow,
  type RoiSettings,
  type UsageSnapshot,
} from "@/lib/api";
import { collectSessions } from "@/lib/sessions";
import { computeSourceRoi, type CostComparison } from "@/lib/roi";
import { SOURCE_META } from "@/lib/sources";
import { clientOf, groupProjectsByClient } from "@/lib/clients";
import { formatDate, formatDecimal, formatMonth, formatUsd } from "@/lib/format";
import { withSource } from "@/lib/routes";

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

export function RoiView({ sources }: RoiViewProps) {
  const { search } = useLocation();
  const [settings, setSettings] = useState<RoiSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [scopeFilter, setScopeFilter] = useState<string>("");
  const [historyRows, setHistoryRows] = useState<DailyProjectRow[]>([]);

  useEffect(() => {
    fetchRoiSettings().then(setSettings).catch((err: Error) => setLoadError(err.message));
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

  if (loadError) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-xl border bg-card p-5 text-sm">
        <AlertCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />
        No se pudo cargar la configuración de ROI ({loadError}).
      </div>
    );
  }
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
        <p className="text-sm text-muted-foreground">
          Los montos de tu plan y la tarifa por hora se editan en{" "}
          <Link to={withSource("/configuracion", search)} className="text-link underline-offset-4 hover:underline">Configuración</Link>.
        </p>
        <label className="block space-y-1.5">
          <span className="block text-xs text-muted-foreground">Acotar a</span>
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
  const subscriptionStart = settings[SUBSCRIPTION_START_KEY[source]];
  const roi = computeSourceRoi({
    source,
    projectCosts: Object.fromEntries(Object.entries(sources?.[source] ?? {}).map(([path, p]) => [path, p.cost])),
    sessions: collectSessions(sources, source),
    historyRows,
    subscriptionCost: settings[SUBSCRIPTION_KEY[source]],
    subscriptionStart,
    hourlyRate: settings.hourly_rate,
    matchesScope,
  });
  const subscriptionMonthly = settings[SUBSCRIPTION_KEY[source]];
  const subscriptionWins = roi.monthly.filter((m) => m.comparison?.winner === "subscription").length;

  return (
    <div className="rounded-xl border bg-card p-5 space-y-3">
      <div className="flex items-center gap-2">
        <meta.icon className="h-4 w-4" style={{ color: meta.color }} aria-hidden />
        <h3 className="text-sm font-medium">{meta.label}</h3>
      </div>

      <Row
        label={subscriptionStart ? `Costo real (API) desde ${formatDate(subscriptionStart)}` : "Costo real (API)"}
        value={formatUsd(roi.apiCost)}
      />
      <Row
        label={subscriptionStart ? `Costo suscripción (${roi.months} ${roi.months === 1 ? "mes" : "meses"})` : "Costo suscripción"}
        value={roi.subscriptionTotal !== null ? formatUsd(roi.subscriptionTotal) : "—"}
      />
      {roi.comparison && <Verdict comparison={roi.comparison} />}

      <div className="h-px bg-border my-1" />

      {subscriptionStart && (
        <p className="text-xs text-muted-foreground">Productividad desde {formatDate(subscriptionStart)}</p>
      )}
      <Row label="Horas de sesión" value={formatDecimal(roi.hours)} />
      <Row label="Valor generado" value={roi.valueGenerated !== null ? formatUsd(roi.valueGenerated) : "—"} />
      {roi.valueGenerated !== null && (
        <Row label="ROI (valor / costo API)" value={roi.roi !== null ? `${formatDecimal(roi.roi)}x` : "—"} emphasize />
      )}

      {roi.monthly.length > 0 && subscriptionStart && (
        <>
          <div className="h-px bg-border my-1" />
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs text-muted-foreground">
              <span>Desglose mensual desde {formatDate(subscriptionStart)}</span>
              {subscriptionMonthly !== null && (
                <span>
                  La suscripción convino en{" "}
                  <span className="font-medium text-foreground tabular-nums">{subscriptionWins} de {roi.monthly.length}</span>{" "}
                  {roi.monthly.length === 1 ? "mes" : "meses"}
                </span>
              )}
            </div>
            <div className="-mx-1 overflow-x-auto px-1">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground text-left">
                  <th className="font-normal py-1">Mes</th>
                  <th className="font-normal py-1 pl-2 text-right">Costo API</th>
                  <th className="hidden font-normal py-1 pl-2 text-right sm:table-cell">Suscripción</th>
                  <th className="font-normal py-1 pl-2 text-right">Conviene</th>
                </tr>
              </thead>
              <tbody>
                {roi.monthly.map(({ key, apiCost, comparison }) => (
                  <tr key={key} className="tabular-nums">
                    <td className="py-1">{formatMonth(key)}</td>
                    <td className="py-1 pl-2 text-right">{formatUsd(apiCost)}</td>
                    <td className="hidden py-1 pl-2 text-right sm:table-cell">{subscriptionMonthly !== null ? formatUsd(subscriptionMonthly) : "—"}</td>
                    <td className="py-1 pl-2 text-right">{comparison ? <WinnerCell comparison={comparison} /> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

const WINNER_LABEL = { subscription: "Suscripción", api: "API", tie: "Empate" } as const;

/** Veredicto explícito para decidir: qué opción es más barata y cuánto ahorra.
 * Se dice con texto (nunca con color o signo), así no hay que interpretar "+/−". */
function Verdict({ comparison }: { comparison: CostComparison }) {
  const title =
    comparison.winner === "subscription"
      ? "Conviene la suscripción"
      : comparison.winner === "api"
        ? "Conviene pagar por uso (API)"
        : "Suscripción y API cuestan lo mismo";
  const detail =
    comparison.winner === "subscription"
      ? "frente a pagar por uso"
      : comparison.winner === "api"
        ? "frente a la suscripción"
        : "";
  return (
    <div className="flex flex-col gap-1 rounded-lg border bg-muted/40 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between sm:gap-3">
      <span className="inline-flex items-center gap-2 font-medium">
        <Scale className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        {title}
      </span>
      {comparison.winner !== "tie" && (
        <span className="pl-6 tabular-nums sm:pl-0 sm:text-right">
          <span className="font-semibold">ahorra {formatUsd(comparison.savings)}</span>
          <span className="text-xs text-muted-foreground sm:block"> {detail}</span>
        </span>
      )}
    </div>
  );
}

function WinnerCell({ comparison }: { comparison: CostComparison }) {
  return (
    <span className="flex flex-col items-end leading-tight">
      <span className={comparison.winner === "subscription" ? "font-medium" : undefined}>{WINNER_LABEL[comparison.winner]}</span>
      {comparison.winner !== "tie" && (
        <span className="text-xs text-muted-foreground whitespace-nowrap">ahorra {formatUsd(comparison.savings)}</span>
      )}
    </span>
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
