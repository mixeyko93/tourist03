type PageLoadingStateProps = {
  className?: string;
  lines?: number;
  blocks?: number;
  columnsClassName?: string;
  blockHeightClassName?: string;
};

export function PageLoadingState({
  className = "",
  lines = 2,
  blocks = 3,
  columnsClassName = "md:grid-cols-3",
  blockHeightClassName = "h-36",
}: PageLoadingStateProps) {
  return (
    <div className={`animate-pulse space-y-4 ${className}`}>
      <div className="space-y-3">
        {Array.from({ length: lines }, (_, index) => (
          <div
            key={index}
            className={`h-4 rounded-full bg-accent/75 dark:bg-accent/55 ${
              index === 0 ? "w-48" : index === 1 ? "w-80 max-w-full" : "w-64 max-w-full"
            }`}
          />
        ))}
      </div>

      <div className={`grid gap-4 ${columnsClassName}`}>
        {Array.from({ length: blocks }, (_, index) => (
          <div key={index} className={`rounded-[1.8rem] border border-border bg-background/60 ${blockHeightClassName}`}>
            <div className="flex h-full flex-col justify-between p-5">
              <div className="space-y-3">
                <div className="h-4 w-28 rounded-full bg-accent/75 dark:bg-accent/55" />
                <div className="h-8 w-20 rounded-2xl bg-accent/90 dark:bg-accent/65" />
              </div>
              <div className="space-y-2">
                <div className="h-3 w-full rounded-full bg-accent/65 dark:bg-accent/45" />
                <div className="h-3 w-3/4 rounded-full bg-accent/55 dark:bg-accent/35" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
