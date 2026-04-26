import QRCode from "qrcode";
import { useEffect, useRef } from "react";

export function QrCanvas({ value, size = 220 }: { value: string; size?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvasRef.current || !value) return;
    void QRCode.toCanvas(canvasRef.current, value, {
      width: size,
      margin: 2,
      color: { dark: "#ffffff", light: "#18181b" },
    });
  }, [value, size]);
  return <canvas ref={canvasRef} width={size} height={size} className="rounded-2xl" />;
}
