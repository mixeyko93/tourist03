import { createRoot, type Root } from "react-dom/client";

import { MapPopup, type MapPopupProps } from "../app/components/MapPopup";

type MountProps = Omit<MapPopupProps, "isOpen">;

type MountedEntry = {
  root: Root;
  props: MountProps;
  hideTimer: number | null;
};

declare global {
  interface Window {
    TouristMapPopupWidget?: {
      mount: (element: HTMLElement, props: MountProps) => void;
      unmount: (element: HTMLElement) => void;
    };
  }
}

const mounted = new WeakMap<HTMLElement, MountedEntry>();

function ensureEntry(element: HTMLElement): MountedEntry {
  const existing = mounted.get(element);
  if (existing) return existing;
  const entry: MountedEntry = {
    root: createRoot(element),
    props: {
      markerType: "hotel",
      onClose: () => undefined,
      data: {
        name: "",
        price: "",
      },
      position: {
        left: 0,
        top: 0,
        width: 360,
        pointerLeft: 180,
      },
    },
    hideTimer: null,
  };
  mounted.set(element, entry);
  return entry;
}

function mount(element: HTMLElement, props: MountProps) {
  const entry = ensureEntry(element);
  if (entry.hideTimer) {
    window.clearTimeout(entry.hideTimer);
    entry.hideTimer = null;
  }
  entry.props = props;
  entry.root.render(<MapPopup {...props} isOpen />);
}

function unmount(element: HTMLElement) {
  const entry = mounted.get(element);
  if (!entry) return;
  if (entry.hideTimer) window.clearTimeout(entry.hideTimer);
  entry.root.render(<MapPopup {...entry.props} isOpen={false} />);
  entry.hideTimer = window.setTimeout(() => {
    entry.root.unmount();
    mounted.delete(element);
  }, 260);
}

window.TouristMapPopupWidget = {
  mount,
  unmount,
};

export {};
