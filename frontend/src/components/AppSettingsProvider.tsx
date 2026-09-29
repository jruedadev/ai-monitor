import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AppSettingsContext, type AppSettingsState } from "@/hooks/appSettingsContext";
import { fetchAppSettings } from "@/lib/api";
import { DEFAULT_CLIENT_ROOTS } from "@/lib/clients";

type Loaded = Omit<AppSettingsState, "reload">;

/** Carga /api/app-settings una vez. Si falla, raíces por defecto y sin redirigir al onboarding. */
export function AppSettingsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Loaded>({
    roots: DEFAULT_CLIENT_ROOTS, completedAt: null, loading: true, error: null, degraded: false,
  });

  const reload = useCallback(async () => {
    try {
      const s = await fetchAppSettings();
      setState({ roots: s.client_roots, completedAt: s.onboarding_completed_at, loading: false, error: null, degraded: s.degraded });
    } catch (err) {
      setState((prev) => ({ ...prev, loading: false, error: (err as Error).message }));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const value = useMemo(() => ({ ...state, reload }), [state, reload]);
  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}
