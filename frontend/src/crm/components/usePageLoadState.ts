import { useEffect, useState } from "react";

export function usePageLoadState(isLoading: boolean) {
  const [hasResolvedOnce, setHasResolvedOnce] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      setHasResolvedOnce(true);
    }
  }, [isLoading]);

  return {
    showInitialSkeleton: isLoading && !hasResolvedOnce,
    showRefreshOverlay: isLoading && hasResolvedOnce,
  };
}
