import { useCallback } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  COMPARE_PARAM, DAY_PARAM, PROJECT_PARAM, SOURCE_PARAM, legacyRedirect, parsePath, parseSource, searchForSource,
  type DashboardLocation,
} from "@/lib/routes";
import type { SourceKey } from "@/lib/sources";

export interface DashboardRoute extends DashboardLocation {
  /** false si la ruta no existe; App redirige a "/". */
  valid: boolean;
  /** Destino de una ruta de la estructura anterior, o null. */
  redirect: string | null;
  source: SourceKey;
  compare: string | null;
  selectedDate: string | null;
  selectedProject: string | null;
  setSelectedDate: (date: string | null) => void;
  setSelectedProject: (project: string | null) => void;
  setSource: (source: SourceKey) => void;
  setCompare: (month: string | null) => void;
}

export function useDashboardRoute(): DashboardRoute {
  const { pathname, search, state } = useLocation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const parsed = parsePath(pathname);

  const setParam = useCallback(
    (key: string, value: string | null, replace: boolean, navState?: unknown) => {
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      }, { replace, state: navState });
    },
    [setParams],
  );

  // El día y el mes comparado reemplazan la entrada del historial (explorar no debe
  // llenar el botón "Atrás"); abrir un proyecto sí la empuja, de modo que "Atrás"
  // cierra el panel de detalle —lo esperable en móvil—.
  const setSelectedDate = useCallback((date: string | null) => setParam(DAY_PARAM, date, true), [setParam]);
  const setCompare = useCallback((month: string | null) => setParam(COMPARE_PARAM, month, true), [setParam]);
  const setSource = useCallback(
    (source: SourceKey) => setParams(new URLSearchParams(searchForSource(search, source)), { replace: true }),
    [search, setParams],
  );
  const setSelectedProject = useCallback(
    (project: string | null) => {
      if (project) {
        setParam(PROJECT_PARAM, project, false, { openedProject: true });
      } else if ((state as { openedProject?: boolean } | null)?.openedProject) {
        navigate(-1);
      } else {
        setParam(PROJECT_PARAM, null, true);
      }
    },
    [navigate, setParam, state],
  );

  return {
    view: parsed?.view ?? "home",
    client: parsed?.client ?? null,
    valid: parsed !== null,
    redirect: parsed ? null : legacyRedirect(pathname, search),
    source: parseSource(params.get(SOURCE_PARAM)),
    compare: params.get(COMPARE_PARAM),
    selectedDate: params.get(DAY_PARAM),
    selectedProject: params.get(PROJECT_PARAM),
    setSelectedDate,
    setSelectedProject,
    setSource,
    setCompare,
  };
}
