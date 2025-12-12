# InfoLobby SPARQL Schema - Estructura Descubierta

Documentación de la estructura real de datos obtenida mediante exploración del endpoint SPARQL.

**Fecha de exploración:** 2025-12-12
**Endpoint:** http://datos.infolobby.cl/sparql
**Default Graph:** http://datos.infolobby.cl/infolobby

---

## Conexión al Endpoint

### Configuración requerida

```
URL: http://datos.infolobby.cl/sparql
Method: GET
Headers:
  - Accept: application/sparql-results+json
  - Referer: http://datos.infolobby.cl/sparql  (REQUERIDO por WAF Fortinet)
Parameters:
  - default-graph-uri: http://datos.infolobby.cl/infolobby
  - query: <SPARQL query URL-encoded>
  - format: application/sparql-results+json
  - timeout: 0
  - debug: on
```

### Ejemplo de URL completa

```
http://datos.infolobby.cl/sparql?default-graph-uri=http%3A%2F%2Fdatos.infolobby.cl%2Finfolobby&query=SELECT+*+WHERE+%7B%3Fs+%3Fp+%3Fo%7D+LIMIT+10&format=application%2Fsparql-results%2Bjson&timeout=0&debug=on
```

### Nota sobre WAF

El endpoint está detrás de un firewall Fortinet que:
- Bloquea requests sin header `Referer`
- Setea cookie `FGTServer` para sesiones
- Algunas librerías Python son bloqueadas (SPARQLWrapper)
- `curl` y `httpx` con headers correctos funcionan

---

## Clases Principales

| Clase RDF | URI Pattern | Cantidad aprox. |
|-----------|-------------|-----------------|
| `cplt:RegistroAudiencia` | `registroaudiencia/{id}` | Miles |
| `cplt:Viaje` | `viaje/{id}` | Miles |
| `cplt:Donativo` | `donativo/{id}` | Cientos |

---

## Audiencias (`cplt:RegistroAudiencia`)

### Query de ejemplo

```sparql
PREFIX cplt: <http://datos.infolobby.cl/ontologia/cplt#>

SELECT ?uri ?codigoURI ?fechaEvento ?datosPasivos ?datosActivos
       ?datosRepresentados ?descripcion ?observaciones
WHERE {
  ?uri a cplt:RegistroAudiencia .
  ?uri cplt:codigoURI ?codigoURI .
  OPTIONAL { ?uri cplt:fechaEvento ?fechaEvento }
  OPTIONAL { ?uri cplt:datosPasivos ?datosPasivos }
  OPTIONAL { ?uri cplt:datosActivos ?datosActivos }
  OPTIONAL { ?uri cplt:datosRepresentados ?datosRepresentados }
  OPTIONAL { ?uri cplt:descripcion ?descripcion }
  OPTIONAL { ?uri cplt:observaciones ?observaciones }
}
LIMIT 100
```

### Campos disponibles

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `codigoURI` | string | ID único | `ab0017839281` |
| `identificadorTemporal` | integer | ID interno temporal | `1249287` |
| `identificadorOtorgaRegistrador` | integer | ID del registrador | `783928` |
| `fechaEvento` | datetime | Fecha y hora de la audiencia | `2025-02-19T16:30:00` |
| `fechaActualizacion` | datetime | Última actualización | `2025-04-03T11:16:16.82` |
| `fechaRegistro` | datetime | Fecha de registro | `2025-04-03T11:16:16.82` |
| `datosPasivos` | string | Funcionario público (nombre, cargo, institución) | `Carolina Tohá Morales: Ministro: SUBSECRETARÍA DEL INTERIOR` |
| `datosActivos` | string | Lobistas (lista separada por `-`) | `Antonio Minte - Fernando Meneses - María Landea` |
| `datosRepresentados` | string | Empresa/entidad representada | `Corporación Chilena de la Madera` |
| `datosMaterias` | string | Materias tratadas | `Elaboración, dictación, modificación...` |
| `descripcion` | string | Lugar de la reunión | `Gabinete de la ministra del Interior...` |
| `observaciones` | string | Tema/objetivo | `Facultades investigativas de incendios forestales` |
| `esDeTipo` | string | Modalidad | `Presencial` |
| `lugar` | uri | Referencia a comuna | `http://datos.infolobby.cl/infolobby/comuna/13101` |
| `materia` | uri | Referencia a materia | `http://datos.infolobby.cl/infolobby/materia/1` |
| `registraFichaPasivo` | uri | Ficha del funcionario | `http://datos.infolobby.cl/infolobby/pasivo/AB001508754` |
| `registradoPor` | uri | Institución registradora | `http://datos.infolobby.cl/infolobby/institucion/ab001` |
| `seeAlsoDev` | uri | Link a ficha web | `http://www.infolobby.cl/Ficha/Audiencia/ab0017839281` |

---

## Viajes (`cplt:Viaje`)

### Query de ejemplo

```sparql
PREFIX cplt: <http://datos.infolobby.cl/ontologia/cplt#>

SELECT ?uri ?codigoURI ?fechaEvento ?descripcion ?datosRazones
       ?datosObjetos ?datosFinancistas ?costo
WHERE {
  ?uri a cplt:Viaje .
  ?uri cplt:codigoURI ?codigoURI .
  OPTIONAL { ?uri cplt:fechaEvento ?fechaEvento }
  OPTIONAL { ?uri cplt:descripcion ?descripcion }
  OPTIONAL { ?uri cplt:datosRazones ?datosRazones }
  OPTIONAL { ?uri cplt:datosObjetos ?datosObjetos }
  OPTIONAL { ?uri cplt:datosFinancistas ?datosFinancistas }
  OPTIONAL { ?uri cplt:costo ?costo }
}
LIMIT 100
```

### Campos disponibles

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `codigoURI` | string | ID único | `ab0017004012` |
| `identificadorTemporal` | integer | ID interno | `889253` |
| `identificadorOtorgaRegistrador` | integer | ID del registrador | `700401` |
| `fechaEvento` | date | Fecha del viaje | `2025-02-14` |
| `fechaActualizacion` | datetime | Última actualización | `2025-04-03T11:08:35.45` |
| `descripcion` | string | Destino del viaje | `Región del Maule` |
| `datosRazones` | string | Motivo del viaje | `Ministra visita la Región del Maule para participar...` |
| `datosObjetos` | string | Tipo de actividad | `Celebraciones, conmemoraciones e inauguraciones` |
| `datosFinancistas` | string | Quien financia | `S/I` (sin información) o nombre |
| `costo` | integer | Costo total | `0` |
| `registraFichaPasivo` | uri | Ficha del funcionario | `http://datos.infolobby.cl/infolobby/pasivo/AB001508754` |
| `registradoPor` | uri | Institución | `http://datos.infolobby.cl/infolobby/institucion/ab001` |
| `seeAlsoDev` | uri | Link a ficha web | `http://www.infolobby.cl/Ficha/Viaje/ab0017004012` |

---

## Donativos (`cplt:Donativo`)

### Query de ejemplo

```sparql
PREFIX cplt: <http://datos.infolobby.cl/ontologia/cplt#>

SELECT ?uri ?codigoURI ?fechaEvento ?descripcion ?ocasion ?datosDonantes
WHERE {
  ?uri a cplt:Donativo .
  ?uri cplt:codigoURI ?codigoURI .
  OPTIONAL { ?uri cplt:fechaEvento ?fechaEvento }
  OPTIONAL { ?uri cplt:descripcion ?descripcion }
  OPTIONAL { ?uri cplt:ocasion ?ocasion }
  OPTIONAL { ?uri cplt:datosDonantes ?datosDonantes }
}
LIMIT 100
```

### Campos disponibles

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `codigoURI` | string | ID único | `ab001627833` |
| `identificadorTemporal` | integer | ID interno | `107101` |
| `identificadorOtorgaRegistrador` | integer | ID del registrador | `62783` |
| `fechaEvento` | date | Fecha del donativo | `2025-06-19` |
| `fechaActualizacion` | datetime | Última actualización | `2025-07-07T16:47:41.81` |
| `descripcion` | string | Qué se donó | `Libro "La esperanza frustrada"` |
| `ocasion` | string | Motivo | `Difusión Ediciones PUCV` |
| `datosDonantes` | string | Quien dona | `Ediciones PUCV` |
| `registraFichaPasivo` | uri | Ficha del receptor | `http://datos.infolobby.cl/infolobby/pasivo/AB001783982` |
| `registradoPor` | uri | Institución | `http://datos.infolobby.cl/infolobby/institucion/ab001` |
| `seeAlsoDev` | uri | Link a ficha web | `http://www.infolobby.cl/Ficha/Donativo/ab001627833` |

---

## Mapeo a Modelo Canónico

| Campo InfoLobby | Modelo LobbyLeaks | Notas |
|-----------------|-------------------|-------|
| `codigoURI` | `externalId` | Prefijado con tipo: `audiencia:ab001...` |
| `fechaEvento` | `fecha` | Parsear datetime/date |
| `datosPasivos` | `Person` (pasivo) | Parsear nombre y cargo |
| `datosActivos` | `Person[]` (activos) | Split por `-` |
| `datosRepresentados` | `Organisation` | Empresa representada |
| `datosDonantes` | `Organisation` | Donante |
| `datosFinancistas` | `Organisation` | Financista viaje |
| `descripcion` | `Event.descripcion` | Contexto |
| `observaciones` | `Event.materia` | Tema tratado |

---

## Queries Útiles para Exploración

### Contar registros por tipo

```sparql
PREFIX cplt: <http://datos.infolobby.cl/ontologia/cplt#>

SELECT ?tipo (COUNT(?s) as ?total) WHERE {
  VALUES ?tipo { cplt:RegistroAudiencia cplt:Viaje cplt:Donativo }
  ?s a ?tipo .
}
GROUP BY ?tipo
```

### Audiencias de un funcionario específico

```sparql
PREFIX cplt: <http://datos.infolobby.cl/ontologia/cplt#>

SELECT ?uri ?fechaEvento ?datosActivos ?observaciones WHERE {
  ?uri a cplt:RegistroAudiencia .
  ?uri cplt:datosPasivos ?pasivo .
  ?uri cplt:fechaEvento ?fechaEvento .
  OPTIONAL { ?uri cplt:datosActivos ?datosActivos }
  OPTIONAL { ?uri cplt:observaciones ?observaciones }
  FILTER(CONTAINS(?pasivo, "Tohá"))
}
ORDER BY DESC(?fechaEvento)
LIMIT 50
```

### Audiencias recientes (último mes)

```sparql
PREFIX cplt: <http://datos.infolobby.cl/ontologia/cplt#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?uri ?codigoURI ?fechaEvento ?datosPasivos ?datosRepresentados WHERE {
  ?uri a cplt:RegistroAudiencia .
  ?uri cplt:codigoURI ?codigoURI .
  ?uri cplt:fechaEvento ?fechaEvento .
  OPTIONAL { ?uri cplt:datosPasivos ?datosPasivos }
  OPTIONAL { ?uri cplt:datosRepresentados ?datosRepresentados }
  FILTER(?fechaEvento >= "2025-11-01"^^xsd:date)
}
ORDER BY DESC(?fechaEvento)
LIMIT 100
```
