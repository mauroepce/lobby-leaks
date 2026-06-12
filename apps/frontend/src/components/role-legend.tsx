const ROLES = [
  { id: "PASIVO", label: "Pasivo (funcionario)", className: "bg-role-PASIVO" },
  { id: "ACTIVO", label: "Activo (lobbista)", className: "bg-role-ACTIVO" },
  { id: "REPRESENTADO", label: "Representado", className: "bg-role-REPRESENTADO" },
  { id: "FINANCIADOR", label: "Financiador", className: "bg-role-FINANCIADOR" },
  { id: "DONANTE", label: "Donante", className: "bg-role-DONANTE" },
] as const;

const NODE_TYPES = [
  { id: "person", label: "Persona", className: "bg-node-person" },
  { id: "organisation", label: "Organización", className: "bg-node-organisation" },
  { id: "event", label: "Evento", className: "bg-node-event" },
] as const;

export function RoleLegend() {
  return (
    <div className="space-y-3 text-xs">
      <div>
        <p className="uppercase tracking-wider text-zinc-500 mb-1">Nodos</p>
        <ul className="space-y-1">
          {NODE_TYPES.map((t) => (
            <li key={t.id} className="flex items-center gap-2">
              <span className={`inline-block size-3 rounded-full ${t.className}`} />
              <span className="text-zinc-300">{t.label}</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <p className="uppercase tracking-wider text-zinc-500 mb-1">Roles (aristas)</p>
        <ul className="space-y-1">
          {ROLES.map((r) => (
            <li key={r.id} className="flex items-center gap-2">
              <span className={`inline-block w-4 h-0.5 ${r.className}`} />
              <span className="text-zinc-300">{r.label}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
