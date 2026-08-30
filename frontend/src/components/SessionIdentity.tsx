interface SessionIdentityProps {
  title: string | null;
  sessionId: string;
  className?: string;
}

/** Muestra el título (si la sesión fue renombrada vía /rename) y siempre
 * el session_id debajo, en mono, para poder ubicarla en disco. */
export function SessionIdentity({ title, sessionId, className }: SessionIdentityProps) {
  return (
    <div className={className}>
      <div className="truncate font-medium" title={title ?? sessionId}>{title ?? sessionId}</div>
      {title && (
        <div className="truncate text-xs text-muted-foreground font-mono" title={sessionId}>
          {sessionId}
        </div>
      )}
    </div>
  );
}
