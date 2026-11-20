import { useState } from "react";
import { AlertCircle, Check, Plus, Save } from "lucide-react";
import { AccountFields } from "@/components/RoiFields";
import { useAppSettings } from "@/hooks/appSettingsContext";
import { errorDetail, saveAppSettings } from "@/lib/api";
import {
  addAccountDraft, removeAccountDraft, setDefaultAccountDraft, updateAccountDraft, validateAccountDrafts,
  type AccountDraft,
} from "@/lib/roiDraft";

export function AccountsForm() {
  const { roots, accounts, reload } = useAppSettings();
  const [draft, setDraft] = useState<AccountDraft[] | null>(null);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const current = draft ?? accounts;
  const edit = (next: AccountDraft[]) => {
    setDraft(next);
    setStatus("idle");
    setError(null);
  };

  const handleSave = async () => {
    const problem = validateAccountDrafts(current);
    if (problem) {
      setError(problem);
      setStatus("error");
      return;
    }
    setStatus("saving");
    setError(null);
    try {
      await saveAppSettings({ client_roots: roots, accounts: current });
      await reload();
      setDraft(null);
      setStatus("saved");
    } catch (err) {
      setError(errorDetail(err) ?? "No se pudo guardar. Revisa que el servidor siga activo e inténtalo de nuevo.");
      setStatus("error");
    }
  };

  return (
    <section aria-labelledby="accounts-title" className="space-y-4 rounded-xl border bg-card p-5">
      <div>
        <h2 id="accounts-title" className="text-sm font-medium">Cuentas de suscripción</h2>
        <p className="text-sm text-muted-foreground">
          Si usas varias cuentas de Claude Code, indica el directorio de configuración de cada una (por ejemplo{" "}
          <code className="font-mono">~/.claude</code>) con su costo mensual y fecha de inicio. El Inicio compara cada una contra la API.
        </p>
      </div>
      <div className="space-y-3">
        {current.map((account) => (
          <AccountFields
            key={account.id}
            account={account}
            onChange={(patch) => edit(updateAccountDraft(current, account.id, patch))}
            onSetDefault={() => edit(setDefaultAccountDraft(current, account.id))}
            onRemove={() => edit(removeAccountDraft(current, account.id))}
            canRemove={removeAccountDraft(current, account.id) !== current}
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => edit(addAccountDraft(current, "claude_code"))}
          className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium"
        >
          <Plus className="h-4 w-4" aria-hidden />Añadir cuenta
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={status === "saving"}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <Save className="h-4 w-4" aria-hidden />
          {status === "saving" ? "Guardando…" : "Guardar cuentas"}
        </button>
        <span role="status" aria-live="polite" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
          {status === "saved" && (<><Check className="h-4 w-4" aria-hidden />Cuentas guardadas</>)}
          {status === "error" && error && (<><AlertCircle className="h-4 w-4 text-destructive" aria-hidden />{error}</>)}
        </span>
      </div>
    </section>
  );
}
