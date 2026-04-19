export function PageRefreshOverlay() {
  return (
    <div className="pointer-events-none absolute inset-0 z-20 overflow-hidden rounded-[inherit] bg-background/44 backdrop-blur-[1.5px]">
      <div className="absolute inset-x-0 top-0 h-1 overflow-hidden">
        <div className="crm-page-refresh-bar h-full w-40 rounded-full" />
      </div>
    </div>
  );
}
