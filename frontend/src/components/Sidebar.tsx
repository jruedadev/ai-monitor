import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Activity, ChevronRight, FolderKanban, LayoutGrid, Scale } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { SOURCE_META } from "@/lib/sources";
import { PROJECT_PARAM, clientPath, sectionPath, type SectionKey } from "@/lib/routes";

const TOOL_SECTIONS = [
  { key: "all", label: "Todo", icon: LayoutGrid, color: undefined },
  { key: "claude_code", ...SOURCE_META.claude_code },
  { key: "codex", ...SOURCE_META.codex },
  { key: "opencode", ...SOURCE_META.opencode },
  { key: "hermes", ...SOURCE_META.hermes },
  { key: "openrouter", ...SOURCE_META.openrouter },
] as const;

interface AppSidebarProps {
  active: SectionKey;
  activeClient: string | null;
  projectsByClient: Record<string, string[]>;
}

function basename(path: string): string {
  return path.split("/").filter(Boolean).pop() ?? path;
}

export function AppSidebar({ active, activeClient, projectsByClient }: AppSidebarProps) {
  const location = useLocation();
  const { isMobile, setOpenMobile } = useSidebar();
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(activeClient ? [activeClient] : []));
  const clients = Object.keys(projectsByClient).sort();

  // Al elegir un cliente se despliegan sus proyectos (sin plegar los demás).
  useEffect(() => {
    if (activeClient) setExpanded((prev) => (prev.has(activeClient) ? prev : new Set(prev).add(activeClient)));
  }, [activeClient]);

  // En móvil el sidebar es un Sheet: navegar lo cierra para mostrar el contenido.
  useEffect(() => {
    if (isMobile) setOpenMobile(false);
  }, [location.pathname, location.search, isMobile, setOpenMobile]);

  const toggleClient = (client: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(client)) next.delete(client);
      else next.add(client);
      return next;
    });

  // Abrir un proyecto conserva la vista actual y solo añade ?proyecto=.
  const projectHref = (path: string) => {
    const params = new URLSearchParams(location.search);
    params.set(PROJECT_PARAM, path);
    return { pathname: location.pathname, search: `?${params}` };
  };

  return (
    <Sidebar>
      <SidebarHeader className="h-16 flex-row items-center gap-2 border-b px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Activity className="h-4 w-4" aria-hidden />
        </div>
        <span className="font-semibold tracking-tight">ai-monitor</span>
      </SidebarHeader>

      <SidebarContent>
        <nav aria-label="Navegación principal" className="contents">
        <SidebarGroup>
          <SidebarGroupLabel>Herramientas</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {TOOL_SECTIONS.map((s) => {
                const isActive = active === s.key && !activeClient;
                return (
                  <SidebarMenuItem key={s.key}>
                    <SidebarMenuButton
                      isActive={isActive}
                      render={<Link to={sectionPath(s.key)} aria-current={isActive ? "page" : undefined} />}
                    >
                      {/* El color de identidad solo en el ícono y solo en la fuente activa. */}
                      <s.icon aria-hidden style={{ color: isActive ? s.color : undefined }} />
                      <span>{s.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Proyectos</SidebarGroupLabel>
          <SidebarGroupContent>
            {clients.length === 0 ? (
              <p className="px-2 text-xs text-muted-foreground">Sin proyectos</p>
            ) : (
              <SidebarMenu>
                {clients.map((client) => {
                  const isActive = activeClient === client;
                  const isExpanded = expanded.has(client);
                  const subId = `client-projects-${client.replace(/\W+/g, "-")}`;
                  return (
                    <SidebarMenuItem key={client}>
                      <SidebarMenuButton
                        isActive={isActive}
                        render={<Link to={clientPath(client)} aria-current={isActive ? "page" : undefined} />}
                      >
                        <FolderKanban aria-hidden />
                        <span>{client}</span>
                      </SidebarMenuButton>
                      <SidebarMenuAction
                        onClick={() => toggleClient(client)}
                        aria-expanded={isExpanded}
                        aria-controls={subId}
                        aria-label={`${isExpanded ? "Ocultar" : "Mostrar"} proyectos de ${client}`}
                      >
                        <ChevronRight aria-hidden className={`transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                      </SidebarMenuAction>
                      {isExpanded && (
                        <SidebarMenuSub id={subId}>
                          {projectsByClient[client].map((path) => (
                            <SidebarMenuSubItem key={path}>
                              <SidebarMenuSubButton size="sm" render={<Link to={projectHref(path)} title={path} />}>
                                <span>{basename(path)}</span>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      )}
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            )}
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Análisis</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={active === "roi"}
                  render={<Link to={sectionPath("roi")} aria-current={active === "roi" ? "page" : undefined} />}
                >
                  {/* Neutro a propósito: el aqua es la identidad de OpenCode y no se recicla. */}
                  <Scale aria-hidden />
                  <span>ROI</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        </nav>
      </SidebarContent>
    </Sidebar>
  );
}
