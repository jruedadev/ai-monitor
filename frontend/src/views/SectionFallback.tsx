import { Skeleton } from "@/components/ui/skeleton";

export function SectionFallback({ label }: { label: string }) {
  return (
    <div aria-busy="true" aria-label={label} className="space-y-3 rounded-xl border bg-card p-5">
      <Skeleton className="h-5 w-56" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}
