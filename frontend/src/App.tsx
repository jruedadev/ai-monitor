import { Navigate } from "react-router-dom";
import { useUsageStream } from "@/hooks/useUsageStream";
import { useDashboardRoute } from "@/hooks/useDashboardRoute";
import { AppSidebar } from "@/components/Sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { ProjectDetailSheet } from "@/components/ProjectDetailSheet";
import { TopBar } from "@/components/TopBar";
import { HomeView } from "@/components/home/HomeView";
import { ActivityView } from "@/views/ActivityView";
import { SpendView } from "@/views/SpendView";
import { ProjectsView } from "@/views/ProjectsView";
import { SettingsView } from "@/views/SettingsView";
import { groupProjectsByClient } from "@/lib/clients";

export default function App() {
  const route = useDashboardRoute();
  const { sources, combined, connected } = useUsageStream();

  if (route.redirect) return <Navigate to={route.redirect} replace />;
  if (!route.valid) return <Navigate to="/" replace />;

  const clients = Object.keys(groupProjectsByClient(Object.keys(combined ?? {}))).sort();

  return (
    <SidebarProvider className="bg-background text-foreground">
      <AppSidebar view={route.view} activeClient={route.client} clients={clients} />
      <SidebarInset className="min-w-0">
        <TopBar
          connected={connected}
          source={route.source}
          onSourceChange={route.setSource}
          sources={sources}
          combined={combined}
        />
        {/* SidebarInset ya es el <main>; aquí un div para no anidar landmarks. */}
        <div key={route.view} className="dashboard-section w-full min-w-0 max-w-[1400px] flex-1 p-4 md:p-6">
          {route.view === "home" && (
            <HomeView source={route.source} compare={route.compare} onCompareChange={route.setCompare} refreshKey={sources} />
          )}
          {route.view === "activity" && (
            <ActivityView
              source={route.source}
              sources={sources}
              selectedDate={route.selectedDate}
              onSelectDate={route.setSelectedDate}
              onSelectProject={route.setSelectedProject}
            />
          )}
          {(route.view === "spend" || route.view === "roi") && (
            <SpendView
              tab={route.view}
              source={route.source}
              sources={sources}
              combined={combined}
              selectedDate={route.selectedDate}
              onSelectDate={route.setSelectedDate}
              onSelectProject={route.setSelectedProject}
            />
          )}
          {route.view === "projects" && (
            <ProjectsView
              client={route.client}
              source={route.source}
              sources={sources}
              combined={combined}
              onSelectProject={route.setSelectedProject}
            />
          )}
          {route.view === "settings" && <SettingsView sources={sources} />}
        </div>
      </SidebarInset>
      <ProjectDetailSheet
        sources={sources}
        section={route.source === "openrouter" ? "all" : route.source}
        project={route.selectedProject}
        onClose={() => route.setSelectedProject(null)}
      />
    </SidebarProvider>
  );
}
