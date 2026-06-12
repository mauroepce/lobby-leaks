"use client";

import { Cosmograph } from "@cosmograph/react";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import type { GraphLink } from "@sdk/models/GraphLink";
import type { GraphNode } from "@sdk/models/GraphNode";

/**
 * The Cosmograph React API expects nodes/links to carry the colour
 * fields it'll read; the LobbyLeaks GraphNode/GraphLink shape is the
 * thin contract surface from the API, so we map once here and feed
 * Cosmograph its own enriched shape.
 *
 * Click on any non-event node → navigate to that node's graph page.
 */

const NODE_COLOR: Record<string, string> = {
  person: "#60a5fa",
  organisation: "#fbbf24",
  event: "#94a3b8",
};

const LINK_COLOR: Record<string, string> = {
  PASIVO: "#3b82f6",
  ACTIVO: "#ef4444",
  REPRESENTADO: "#f59e0b",
  FINANCIADOR: "#8b5cf6",
  DONANTE: "#10b981",
};

type CosmoNode = {
  id: string;
  type: string;
  label: string;
  color: string;
  size: number;
};

type CosmoLink = {
  source: string;
  target: string;
  label: string;
  color: string;
};

export function GraphView({
  centerId,
  nodes,
  links,
}: {
  centerId: string;
  nodes: GraphNode[];
  links: GraphLink[];
}) {
  const router = useRouter();

  const cosmoNodes = useMemo<CosmoNode[]>(
    () =>
      nodes.map((n) => ({
        id: n.id,
        type: n.type,
        label: n.label ?? n.id,
        color: NODE_COLOR[n.type] ?? "#a1a1aa",
        size: n.id === centerId ? 12 : n.type === "event" ? 4 : 6,
      })),
    [nodes, centerId],
  );

  const cosmoLinks = useMemo<CosmoLink[]>(
    () =>
      links.map((l) => ({
        source: l.source,
        target: l.target,
        label: l.label,
        color: LINK_COLOR[l.label] ?? "#71717a",
      })),
    [links],
  );

  return (
    <div className="w-full h-[70vh] rounded-md border border-zinc-800 overflow-hidden bg-black">
      <Cosmograph
        nodes={cosmoNodes}
        links={cosmoLinks}
        nodeColor={(n: CosmoNode) => n.color}
        nodeSize={(n: CosmoNode) => n.size}
        nodeLabelAccessor={(n: CosmoNode) => n.label}
        linkColor={(l: CosmoLink) => l.color}
        linkWidth={1}
        linkArrows={true}
        backgroundColor="#000000"
        showFPSMonitor={false}
        onClick={(node?: CosmoNode) => {
          // Click empty area = no-op; click an event = no-op (events
          // have no "graph page"); click another entity = navigate.
          if (!node || node.id === centerId || node.type === "event") return;
          router.push(`/graph/${encodeURIComponent(node.id)}`);
        }}
      />
    </div>
  );
}
