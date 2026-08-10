import { useEffect, useRef, useState } from "react";

// Animate a number from `start` to `target` with an ease-out curve.
export function useCountUp(target, { duration = 1000, decimals = 0, start = 0 } = {}) {
  const [val, setVal] = useState(start);
  const raf = useRef();

  useEffect(() => {
    const from = start;
    const diff = target - from;
    const t0 = performance.now();

    const tick = (t) => {
      const p = Math.min(1, (t - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(from + diff * eased);
      if (p < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line
  }, [target, duration]);

  return decimals ? Number(val.toFixed(decimals)) : Math.round(val);
}
