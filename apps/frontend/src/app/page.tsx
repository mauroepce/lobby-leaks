import { SearchInput } from "@/components/search-input";
import { SearchResults } from "@/components/search-results";
import { ApiError, searchEntities } from "@/lib/api";

export const dynamic = "force-dynamic"; // every request re-runs the search

export default async function Home({
  searchParams,
}: {
  searchParams: { q?: string };
}) {
  const query = (searchParams.q ?? "").trim();
  const showResults = query.length > 0;

  let resultsBlock: React.ReactNode = null;
  if (showResults) {
    try {
      const data = await searchEntities(query);
      resultsBlock = (
        <SearchResults results={data.results} total={data.total} query={query} />
      );
    } catch (err) {
      const message =
        err instanceof ApiError
          ? `Error ${err.status} consultando la API.`
          : "No se pudo conectar a la API.";
      resultsBlock = (
        <p className="text-sm text-red-400">
          {message}{" "}
          <span className="text-zinc-500">
            ¿Está corriendo <code>apps/api</code>?
          </span>
        </p>
      );
    }
  }

  return (
    <section className="px-6 py-12 max-w-3xl mx-auto space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">
          Triangulación lobby + dinero + decisiones
        </h1>
        <p className="text-sm text-zinc-400">
          Buscá una persona o empresa. Hacé click en un resultado para ver su
          subgrafo de relaciones (audiencias, viajes, donativos).
        </p>
      </div>
      <SearchInput defaultValue={query} />
      {resultsBlock}
      {!showResults ? (
        <p className="text-sm text-zinc-500">
          Probá: <code>corfo</code>, <code>ministerio</code>, un apellido o un
          RUT.
        </p>
      ) : null}
    </section>
  );
}
