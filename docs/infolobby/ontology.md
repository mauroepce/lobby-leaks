# 📚 Ontología de la Ley del Lobby (InfoLobby) – Resumen Operativo

**Versión:** 2.0  
**Namespace principal:** `cplt:`  
**URI:** http://datos.infolobby.cl/ontologia/cplt#  

**SPARQL Endpoint:** http://datos.infolobby.cl/sparql  
**Default Graph:** http://datos.infolobby.cl/infolobby  

---

## 🎯 Propósito de la Ontología

Definir un **modelo semántico único** para representar:

- Audiencias  
- Viajes  
- Donativos  

Relacionando:

- Personas  
- Entidades (empresas / instituciones)  
- Cargos públicos  
- Tiempos  
- Montos  
- Roles (activo / pasivo / asistente / financista)  

Esta ontología está diseñada para **transparencia y trazabilidad**.

---

## 🧱 Clases principales (las que realmente usarás)

### 📌 Eventos (Agenda Pública)

| Clase | Descripción |
|------|-------------|
| `cplt:AgendaPublica` | Evento público base |
| `cplt:RegistroAudiencia` | Reunión / audiencia |
| `cplt:Viaje` | Viaje oficial |
| `cplt:Donativo` | Aporte económico |

---

### 👤 Personas y Roles

| Clase | Significado |
|------|-------------|
| `cplt:Persona` | Persona (equiv. `foaf:Person`) |
| `cplt:Pasivo` | Persona con cargo público |
| `cplt:Activo` | Persona privada |
| `cplt:Asistente` | Asistente a evento |
| `cplt:DonanteActivo` | Persona que dona |
| `cplt:DonanteEntidad` | Empresa que dona |
| `cplt:FinancistaViaje` | Persona que financia viaje |
| `cplt:FinancistaViajeEntidad` | Empresa que financia viaje |

---

### 🏢 Organizaciones

| Clase | Significado |
|------|-------------|
| `cplt:Entidad` | Empresa / fundación privada |
| `cplt:Institucion` | Órgano público |
| `cplt:RegistroEntidad` | Relación entidad ↔ evento |

---

### ⏱️ Tiempo

| Clase | Uso |
|------|-----|
| `cplt:AudienciaTiempoInstante` | Inicio audiencia |
| `cplt:AudienciaTiempoIntervalo` | Duración |
| `cplt:ViajeTiempoInstanteInicio` | Inicio viaje |
| `cplt:ViajeTiempoInstanteFinal` | Fin viaje |
| `cplt:DonativoTiempoInstante` | Fecha donativo |

---

## 🔗 Propiedades clave (para SPARQL)

### Identidad

| Propiedad | Uso |
|----------|-----|
| `cplt:rut` | RUT persona o entidad |
| `cplt:identificadorTemporal` | ID temporal |
| `cplt:identificadorOtorgaRegistrador` | ID del sistema |

---

### Relaciones principales

| Propiedad | Significado |
|----------|-------------|
| `cplt:registraAgendaPublica` | Relaciona evento |
| `cplt:tieneRelacionCon` | Relación genérica |
| `cplt:participa` | Participación en evento |
| `cplt:participaComoPasivo` | Rol público |
| `cplt:participaComoActivo` | Rol privado |
| `cplt:financia` / `cplt:financista` | Financiamiento |
| `cplt:dono` / `cplt:donadoPor` | Donación |
| `cplt:otorgadoA` / `cplt:recibe` | Receptor donativo |

---

### Atributos útiles

| Propiedad | Uso |
|----------|-----|
| `cplt:monto` | Monto en dinero |
| `cplt:fechaRealizado` | Fecha |
| `cplt:lugar` | Ubicación |
| `cplt:materia` | Tema tratado |
| `cplt:observaciones` | Texto libre |

---

## 🧠 Mapeo a tu modelo canónico

| Ontología | Tu modelo |
|----------|-----------|
| `cplt:Persona` | `Person` |
| `cplt:Entidad` / `cplt:Institucion` | `Organisation` |
| `cplt:RegistroAudiencia` | `Event(type='audiencia')` |
| `cplt:Viaje` | `Event(type='viaje')` |
| `cplt:Donativo` | `Contribution` |
| `cplt:financia` | `Edge(type='FINANCES')` |
| `cplt:participa` | `Edge(type='PARTICIPATES')` |

---

## 🔍 Ejemplo mental de query SPARQL

**“Audiencias donde una empresa se reunió con un ministro”**

```sparql
SELECT ?audiencia ?persona ?empresa ?fecha
WHERE {
  ?audiencia a cplt:RegistroAudiencia .
  ?audiencia cplt:participaComoPasivo ?persona .
  ?audiencia cplt:participaComoActivo ?empresa .
  ?audiencia cplt:fechaRealizado ?fecha .
}
LIMIT 100
