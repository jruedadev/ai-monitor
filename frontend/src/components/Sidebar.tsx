import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Activity, FolderKanban, Home, Lightbulb, Settings, Wallet } from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent, SidebarHeader, SidebarMenu,
  SidebarMenuBadge, SidebarMenuButton, SidebarMenuItem, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem, useSidebar,
} from "@/components/ui/sidebar";
import { viewPath, withSource, type ViewKey } from "@/lib/routes";

// Activo = borde interno cyan de 2px + superficie soft (spec §4.2).
const ACTIVE = "data-active:shadow-[inset_2px_0_0_var(--primary)]";

const NAV: { views: ViewKey[]; to: ViewKey; label: string; icon: typeof Home }[] = [
  { views: ["home"], to: "home", label: "Inicio", icon: Home },
  { views: ["activity"], to: "activity", label: "Actividad", icon: Activity },
  { views: ["spend", "roi"], to: "spend", label: "Gasto y ROI", icon: Wallet },
  { views: ["projects"], to: "projects", label: "Proyectos", icon: FolderKanban },
];

interface AppSidebarProps {
  view: ViewKey;
  activeClient: string | null;
  clients: string[];
}

export function AppSidebar({ view, activeClient, clients }: AppSidebarProps) {
  const location = useLocation();
  const { isMobile, setOpenMobile } = useSidebar();
  const href = (to: string) => withSource(to, location.search);

  // En móvil el sidebar es un Sheet: navegar lo cierra para mostrar el contenido.
  useEffect(() => {
    if (isMobile) setOpenMobile(false);
  }, [location.pathname, location.search, isMobile, setOpenMobile]);

  return (
    <Sidebar>
      <SidebarHeader className="h-16 flex-row items-center gap-2 border-b px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[image:var(--gradient-brand)] text-primary-foreground">
          <Activity className="h-4 w-4" aria-hidden />
        </div>
        <span className="bg-[image:var(--gradient-brand)] bg-clip-text font-extrabold tracking-tight text-transparent">ai-monitor</span>
      </SidebarHeader>

      <SidebarContent>
        <nav aria-label="Navegación principal" className="contents">
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV.map((item) => {
                  const isActive = item.views.includes(view) && !(item.to === "projects" && activeClient);
                  return (
                    <SidebarMenuItem key={item.to}>
                      <SidebarMenuButton
                        isActive={item.views.includes(view)}
                        className={ACTIVE}
                        render={<Link to={href(viewPath(item.to))} aria-current={isActive ? "page" : undefined} />}
                      >
                        <item.icon aria-hidden />
                        <span>{item.label}</span>
                      </SidebarMenuButton>
                      {item.to === "projects" && clients.length > 0 && (
                        <SidebarMenuSub>
                          {clients.map((client) => (
                            <SidebarMenuSubItem key={client}>
                              <SidebarMenuSubButton
                                size="sm"
                                isActive={activeClient === client}
                                render={
                                  <Link
                                    to={href(viewPath("projects", client))}
                                    aria-current={activeClient === client ? "page" : undefined}
                                  />
                                }
                              >
                                <span>{client}</span>
                              </SidebarMenuSubButton>
                            </SidebarMenuSubItem>
                          ))}
                        </SidebarMenuSub>
                      )}
                    </SidebarMenuItem>
                  );
                })}
                <SidebarMenuItem>
                  <SidebarMenuButton disabled aria-disabled="true">
                    <Lightbulb aria-hidden />
                    <span>Recomendaciones</span>
                  </SidebarMenuButton>
                  <SidebarMenuBadge>pronto</SidebarMenuBadge>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </nav>
      </SidebarContent>

      <SidebarFooter className="border-t">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              isActive={view === "settings"}
              className={ACTIVE}
              render={<Link to={href(viewPath("settings"))} aria-current={view === "settings" ? "page" : undefined} />}
            >
              <Settings aria-hidden />
              <span>Configuración</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
