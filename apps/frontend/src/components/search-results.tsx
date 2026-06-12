import Link from "next/link";

import type { EntityResult } from "@sdk/models/EntityResult";

const TYPE_LABEL: Record<string, string> = {
  person: "Persona",
  organisation: "Organización",
};

const TYPE_PILL_CLASS: Record<string, string> = {
  person: "bg-node-person/10 text-node-person",
  organisation: "bg-node-organisation/10 text-node-organisation",
};

export function SearchResults({
  results,
  total,
  query,
}: {
  results: EntityResult[];
  total: number;
  query: string;
}) {
  if (results.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        Sin resultados para <span className="text-zinc-300">{query}</span>.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-500">
        {total} resultado{total === 1 ? "" : "s"} · mostrando {results.length}
      </p>
      <ul className="divide-y divide-zinc-800 border border-zinc-800 rounded-md overflow-hidden">
        {results.map((r) => (
          <li key={r.id}>
            <Link
              href={`/graph/${r.id}`}
              className="
                flex items-center justify-between gap-3 px-4 py-3
                hover:bg-zinc-900/50 transition-colors
              "
            >
              <div className="min-w-0">
                <p className="text-sm text-zinc-100 truncate">{r.label}</p>
                {r.rut ? (
                  <p className="text-xs text-zinc-500">RUT {r.rut}</p>
                ) : null}
              </div>
              <span
                className={`
                  text-xs font-medium px-2 py-1 rounded
                  ${TYPE_PILL_CLASS[r.type] ?? "bg-zinc-800 text-zinc-400"}
                `}
              >
                {TYPE_LABEL[r.type] ?? r.type}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
