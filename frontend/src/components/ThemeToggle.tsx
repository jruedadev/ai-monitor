import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/useTheme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <Button variant="outline" size="sm" onClick={toggle}>
      {theme === "dark" ? "☀️ Claro" : "🌙 Oscuro"}
    </Button>
  );
}
