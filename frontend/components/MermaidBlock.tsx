"use client";

import { useEffect, useRef } from "react";
import mermaid from "mermaid";

type Props = {
  chart: string;
};

export function MermaidBlock({ chart }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    mermaid.initialize({ startOnLoad: false, theme: "base", securityLevel: "strict" });
    if (!ref.current) return;
    const id = `diagram-${Math.random().toString(36).slice(2)}`;
    mermaid.render(id, chart).then(({ svg }) => {
      if (ref.current) ref.current.innerHTML = svg;
    });
  }, [chart]);

  return <div className="mermaid-frame" ref={ref} aria-label="Mermaid diagram" />;
}

