import { useEffect, useRef, useState } from "react";

export function usePageLoadState(isLoading: boolean) {
  const [hasResolvedOnce, setHasResolvedOnce] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!isLoading && !hasResolvedOnce) {
      // Небольшая пауза после загрузки данных — дать React время отрендерить контент
      // до того как анимация начнётся. Убирает мерцание при быстрых ответах сервера.
      timerRef.current = setTimeout(() => {
        setHasResolvedOnce(true);
        setIsVisible(true);
      }, 60);
    } else if (!isLoading && hasResolvedOnce) {
      setIsVisible(true);
    }

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isLoading, hasResolvedOnce]);

  return {
    showInitialSkeleton: isLoading && !hasResolvedOnce,
    showRefreshOverlay: isLoading && hasResolvedOnce,
    isPageVisible: isVisible,
  };
}
