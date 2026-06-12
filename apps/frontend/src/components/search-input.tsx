/**
 * The search input lives in a form, so submitting it just rewrites the
 * URL with `?q=...`. The page below reads `searchParams.q` and re-runs
 * the server-side fetch on the new value — no client-side state needed.
 */

export function SearchInput({ defaultValue }: { defaultValue?: string }) {
  return (
    <form
      action="/"
      method="get"
      className="w-full max-w-xl flex items-center gap-2"
    >
      <input
        type="search"
        name="q"
        defaultValue={defaultValue}
        autoFocus
        placeholder="Buscar persona u organización (nombre o RUT)..."
        className="
          flex-1 rounded-md bg-zinc-900 border border-zinc-700
          px-3 py-2 text-sm text-zinc-100
          placeholder:text-zinc-500
          focus:outline-none focus:ring-2 focus:ring-blue-500
        "
      />
      <button
        type="submit"
        className="
          rounded-md bg-blue-500 hover:bg-blue-400
          px-4 py-2 text-sm font-medium text-zinc-50
        "
      >
        Buscar
      </button>
    </form>
  );
}
