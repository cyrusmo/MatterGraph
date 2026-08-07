import { useEffect, useState } from "react";

/**
 * Tracks which section is currently dominant in the viewport so the rail can mark it.
 * Pass a stable array — define it outside the component, not inline.
 */
export function useSectionSpy(ids: readonly string[]): string {
  const [active, setActive] = useState(ids[0] ?? "");

  useEffect(() => {
    const ratios = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          ratios.set(entry.target.id, entry.intersectionRatio);
        }
        let best = "";
        let bestRatio = 0;
        for (const [id, ratio] of ratios) {
          if (ratio > bestRatio) {
            best = id;
            bestRatio = ratio;
          }
        }
        if (best) {
          setActive(best);
        }
      },
      { threshold: [0, 0.2, 0.5, 0.85] },
    );

    for (const id of ids) {
      const element = document.getElementById(id);
      if (element) {
        observer.observe(element);
      }
    }
    return () => observer.disconnect();
  }, [ids]);

  return active;
}
