# Métricas propias — `/metricas/`

Página con **3 métricas diseñadas con IA** para Aurora. Miden cosas que los KPIs
clásicos no capturan: el **esfuerzo** del asociado al conversar, el **dinero**
realmente recuperado y qué tan **vieja** es la mora (no solo cuánta hay).

## Cómo funciona

- Cada métrica se **calcula en vivo** desde la base de datos (Supabase) con SQL.
- Cada tarjeta muestra: el **valor**, un **semáforo** y una línea **"Qué mide"**
  en lenguaje simple, más la **meta**.
- Si falta la tabla que la alimenta, aparece **"Sin datos aún"** con lo que hace
  falta, sin inventar cifras.

**Semáforo:** 🟢 En objetivo · 🟠 Alerta naranja · 🔴 Alerta roja · ⚪ Sin datos aún

Código: `landing/metricas.py` (cálculo) · `landing/templates/landing/metricas.html` (vista).

---

## Las 3 métricas

### 1. Índice de fricción conversacional
- **Qué mide:** cuánto esfuerzo (mensajes) le cuesta al asociado llegar a la
  respuesta. **Menos es mejor.**
- **Cómo se calcula:** promedio de mensajes del usuario por conversación (suma
  las veces que tuvo que repetir o insistir).
- **Meta:** ideal ≤ 3 · 🟠 más de 4 · 🔴 más de 6.
- **Para qué sirve:** la auto-contención dice *cuántas* conversaciones resuelve
  el bot; esta dice si las resuelve *bien* o frustrando al asociado.

### 2. Eficiencia de campaña de cobranza
- **Qué mide:** de cada $100 vencidos, cuántos pesos realmente volvieron a caja.
  **Más alto es mejor.**
- **Cómo se calcula:** dinero recuperado (pagos exitosos) ÷ valor de las cuotas
  en mora, en pesos.
- **Meta:** objetivo ≥ 40% · 🔴 menos de 20%.
- **Para qué sirve:** no cuenta *cuántos* pagos hubo, sino *cuánto valor* se
  recuperó (un pago grande vale más que diez pequeños).

### 3. Índice de salud de cartera ponderado
- **Qué mide:** una nota de 0 a 100 de la cartera; castiga más las deudas más
  viejas. **Más alto = más sana.**
- **Cómo se calcula:** 100 − deterioro, donde cada saldo en mora pesa según su
  antigüedad (una cuota de 60 días pesa mucho más que una de 5).
- **Meta:** sana ≥ 85 · 🟠 menos de 85 · 🔴 menos de 70.
- **Para qué sirve:** dos carteras con el mismo % de mora pueden tener salud muy
  distinta según qué tan atrasadas estén las deudas.
