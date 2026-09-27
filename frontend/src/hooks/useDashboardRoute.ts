import { useCallback } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { DAY_PARAM, PROJECT_PARAM, parsePath, type DashboardLocation } from "@/lib/routes";

export interface DashboardRoute extends DashboardLocation {
  /** false si la ruta no existe; App redirige a "/". */
  valid: boolean;
  selectedDate: string | null;
  selectedProject: string | null;
  setSelectedDate: (date: string | null) => void;
  setSelectedProject: (project: string | null) => void;
}

export function useDashboardRoute(): DashboardRoute {
  const { pathname, state } = useLocation();
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

  // El día reemplaza la entrada del historial (explorar la gráfica no debe
  // llenar el botón "Atrás"); abrir un proyecto sí la empuja, de modo que
  // "Atrás" cierra el panel de detalle —lo esperable en móvil—.
  const setSelectedDate = useCallback((date: string | null) => setParam(DAY_PARAM, date, true), [setParam]);
  const setSelectedProject = useCallback(
    (project: string | null) => {
      if (project) {
        setParam(PROJECT_PARAM, project, false, { openedProject: true });
      } else if ((state as { openedProject?: boolean } | null)?.openedProject) {
        // Lo abrimos nosotros con push: volver atrás lo cierra sin dejar una
        // entrada "con panel" a la que "Atrás" regresaría.
        navigate(-1);
      } else {
        // Llegó por enlace directo: no hay entrada previa propia, se quita en sitio.
        setParam(PROJECT_PARAM, null, true);
      }
    },
    [navigate, setParam, state],
  );

  return {
    section: parsed?.section ?? "all",
    client: parsed?.client ?? null,
    valid: parsed !== null,
    selectedDate: params.get(DAY_PARAM),
    selectedProject: params.get(PROJECT_PARAM),
    setSelectedDate,
    setSelectedProject,
  };
}
