import { createContext, useContext } from "react";
import type { Account } from "@/lib/api";
import { DEFAULT_CLIENT_ROOTS, type ClientRoot } from "@/lib/clients";

export interface AppSettingsState {
  roots: ClientRoot[];
  accounts: Account[];
  completedAt: string | null;
  loading: boolean;
  error: string | null;
  degraded: boolean;
  reload: () => Promise<void>;
}

const FALLBACK: AppSettingsState = {
  roots: DEFAULT_CLIENT_ROOTS,
  accounts: [],
  completedAt: null,
  loading: false,
  error: "AppSettingsProvider ausente",
  degraded: false,
  reload: async () => {},
};

export const AppSettingsContext = createContext<AppSettingsState>(FALLBACK);

export function useAppSettings(): AppSettingsState {
  return useContext(AppSettingsContext);
}

export function useClientRoots(): ClientRoot[] {
  return useContext(AppSettingsContext).roots;
}
