# Dashboard de KPIs — `/kpis/`

Página con los **6 indicadores ejecutivos** de Aurora Financiera. Sirve para ver
de un vistazo si la transformación digital está funcionando.

## Cómo funciona

- Cada KPI se **calcula en vivo** desde la base de datos (Supabase) con una
  consulta SQL. No hay cifras escritas a mano.
- Cada tarjeta muestra: el **valor**, un **semáforo** de estado y una línea
  **"Qué mide"** en lenguaje simple, más la **meta**.
- Si una tabla todavía no tiene datos, el KPI aparece como **"Sin datos aún"** y
  explica qué falta para poder calcularlo (en vez de mostrar un número falso).

**Semáforo:**
🟢 En objetivo · 🟠 Alerta naranja · 🔴 Alerta roja · ⚪ Sin datos aún

Código: `landing/kpis.py` (cálculo) · `landing/templates/landing/kpi-dashboard.html` (vista).

---

## Los 6 KPIs

| # | KPI | Qué mide (simple) | Cómo se calcula | Meta |
|---|-----|-------------------|-----------------|------|
| 1 | **Auto-contención** | De cada 100 conversaciones, cuántas resolvió el bot solo, sin pasar a un humano. | Conversaciones sin escalar ÷ conversaciones totales | 🔴 si baja de 60% |
| 2 | **Tiempo de 1ª respuesta (humano)** | Cuánto tarda un asesor en responder cuando el bot le pasa el caso. | Promedio de tiempo hasta la primera respuesta del agente | 🟠 si supera 3 min |
| 3 | **Conversión de campañas de cobranza** | De cada 100 mensajes de cobranza, cuántos terminaron en pago. | Pagos generados ÷ mensajes enviados | 🔴 si baja de 5% |
| 4 | **NPS Aurora** | Qué tan dispuestos están los asociados a recomendar Aurora. | % promotores (9–10) − % detractores (0–6) | 🟠 si cae bajo 40 |
| 5 | **Abandono de onboarding digital** | De cada 100 que empiezan a afiliarse, cuántas dejan el proceso a medias. | Flujos iniciados sin completar ÷ total iniciados | 🔴 si supera 15% |
| 6 | **Recuperación de mora temprana** | De los que tienen 1–30 días de atraso, cuántos se pusieron al día. | Asociados que pagaron ÷ asociados en mora 1–30 días | 🟠 si baja de 30% |

> Los KPIs 2, 3 y 4 aún salen **"Sin datos aún"** porque dependen de datos que
> todavía no se registran (tiempos de agente, campañas enviadas y una encuesta
> de satisfacción). El dashboard lo indica en cada tarjeta.

---

## Indicador extra (abajo del todo)

**Tasa de mora general** = asociados en mora ÷ total de asociados con saldo.
Es un indicador de **negocio**, no una alerta diaria: tarda meses en moverse.
Referencia del sector: 9%.
