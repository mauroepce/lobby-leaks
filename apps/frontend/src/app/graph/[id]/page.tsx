import Link from "next/link";
import { notFound } from "next/navigation";

import { RoleLegend } from "@/components/role-legend";
import { ApiError, fetchSubgraph } from "@/lib/api";

import { GraphView } from "./graph-view";

export const dynamic = "force-dynamic";

export default async function GraphPage({
  params,
}: {
  params: { id: string };
}) {
  const id = decodeURIComponent(params.id);

  let data;
  try {
    data = await fetchSubgraph(id, { depth: 2, limitEvents: 50 });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    return (
      <section className="px-6 py-12 max-w-3xl mx-auto">
        <p className="text-sm text-red-400">
          Error consultando el subgrafo. ¿Está corriendo <code>apps/api</code>?
        </p>
        <Link href="/" className="text-sm text-blue-400 underline">
          ← Volver a buscar
        </Link>
      </section>
    );
  }

  const centerNode = data.nodes.find((n) => n.id === data.center);
  const centerLabel = centerNode?.label ?? data.center;
  const centerType = centerNode?.type ?? "entidad";

  return (
    <section className="px-6 py-8 max-w-7xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div className="space-y-1 min-w-0">
          <p className="text-xs uppercase tracking-wider text-zinc-500">
            {centerType}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight truncate">
            {centerLabel}
          </h1>
          <p className="text-xs text-zinc-500">
            {data.nodes.length} nodos · {data.links.length} aristas · profundidad{" "}
            {data.depth}
            {data.truncated ? (
              <span className="ml-2 inline-block px-2 py-0.5 rounded bg-amber-500/10 text-amber-300">
                truncado — mostrando los primeros {data.links.length} resultados
              </span>
            ) : null}
          </p>
          <Link
            href="/"
            className="inline-block mt-2 text-sm text-blue-400 hover:underline"
          >
            ← Buscar otra entidad
          </Link>
        </div>
        <aside className="shrink-0">
          <RoleLegend />
        </aside>
      </div>
      <GraphView centerId={data.center} nodes={data.nodes} links={data.links} />
      <p className="text-xs text-zinc-500">
        Click en un nodo Persona u Organización para abrir su subgrafo. Los
        nodos Evento no son navegables (representan audiencias, viajes y
        donativos).
      </p>
    </section>
  );
}
