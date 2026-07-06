"""
Diseñador de métricas con IA — 3 métricas NO estándar de Aurora Financiera.

A diferencia de los 6 KPIs ejecutivos (`kpis.py`), que miden las promesas del
comité con indicadores convencionales, estas métricas fueron *diseñadas con
asistencia de IA*: combinan señales que normalmente no se cruzan (esfuerzo
conversacional, recuperación monetaria, severidad de la mora) para revelar cosas
que un KPI clásico no ve. Se calculan EN VIVO con SQL crudo sobre Supabase; si la
tabla que alimenta una métrica está vacía, se marca `disponible=False` y se
explica qué falta — misma filosofía de `kpis.py`: no se inventan cifras.

Las tres métricas:
    1. Índice de fricción conversacional  (sobre n8n_chat_histories)
    2. Eficiencia de campaña de cobranza   (pagos vs. cuotas en mora)
    3. Índice de salud de cartera ponderado (mora ponderada por antigüedad)

`compute_metricas()` devuelve una lista de dicts lista para la plantilla.
"""
from django.db import connection


def _scalar(sql, params=None):
    """Ejecuta una consulta que devuelve un único valor. None si no hay filas."""
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def _row(sql, params=None):
    """Ejecuta una consulta que devuelve una sola fila (o None)."""
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchone()


def _pct(numerador, denominador):
    """Porcentaje seguro (evita división por cero). Devuelve float redondeado."""
    if not denominador:
        return 0.0
    return round(numerador / denominador * 100, 1)


def _cop(valor):
    """Formatea un monto en pesos colombianos: 1005000 -> '$1.005.000'."""
    try:
        entero = int(round(float(valor)))
    except (TypeError, ValueError):
        return '$0'
    return '$' + f'{entero:,}'.replace(',', '.')


def _estado(valor, *, rojo=None, naranja=None, mayor_es_peor=True):
    """
    Devuelve 'rojo' / 'naranja' / 'ok' comparando `valor` contra umbrales.
    `mayor_es_peor=True`  → un valor ALTO dispara alerta (ej. fricción).
    `mayor_es_peor=False` → un valor BAJO dispara alerta (ej. salud de cartera).
    """
    if valor is None:
        return 'sin_datos'
    if mayor_es_peor:
        if rojo is not None and valor > rojo:
            return 'rojo'
        if naranja is not None and valor > naranja:
            return 'naranja'
    else:
        if rojo is not None and valor < rojo:
            return 'rojo'
        if naranja is not None and valor < naranja:
            return 'naranja'
    return 'ok'


# ---------------------------------------------------------------------------
# Métrica 1 — Índice de fricción conversacional
# ---------------------------------------------------------------------------
# Idea (no estándar): un KPI de contención dice CUÁNTAS conversaciones resuelve
# el bot, pero no CUÁNTO le cuesta al asociado llegar a la respuesta. La fricción
# mide el esfuerzo: mensajes de usuario por conversación + repeticiones (cuando
# alguien tiene que reformular o insistir con el mismo texto). Mucha fricción =
# el bot resuelve, pero mal (frustra). Se lee sobre el historial real del chat.
def _metrica_friccion():
    sesiones = _scalar(
        "SELECT count(DISTINCT session_id) FROM n8n_chat_histories"
    ) or 0
    if not sesiones:
        return dict(disponible=False, valor=None)

    msgs_usuario = _scalar(
        "SELECT count(*) FROM n8n_chat_histories WHERE message->>'type' = 'human'"
    ) or 0

    # Reintentos: mismo texto de usuario repetido dentro de una sesión (insistió
    # o reformuló). Sumamos las repeticiones (n-1 por grupo) y en cuántas sesiones.
    fila = _row(
        "SELECT COALESCE(sum(n - 1), 0), count(DISTINCT session_id) FROM ("
        "  SELECT session_id, message->>'content' AS c, count(*) AS n"
        "  FROM n8n_chat_histories"
        "  WHERE message->>'type' = 'human'"
        "  GROUP BY session_id, message->>'content'"
        "  HAVING count(*) > 1"
        ") t"
    )
    reintentos, sesiones_con_reintento = (fila[0] or 0, fila[1] or 0) if fila else (0, 0)

    # El índice es el promedio de mensajes de usuario por conversación:
    # 2-3 = fluido; >4 empieza a costar; >6 el asociado está peleando con el bot.
    valor = round(msgs_usuario / sesiones, 1) if sesiones else 0.0
    return dict(
        disponible=True, valor=valor,
        sesiones=sesiones, msgs_usuario=msgs_usuario,
        reintentos=reintentos, sesiones_con_reintento=sesiones_con_reintento,
    )


# ---------------------------------------------------------------------------
# Métrica 2 — Eficiencia de campaña de cobranza
# ---------------------------------------------------------------------------
# Idea (no estándar): no cuenta cuántos pagos hubo, sino qué PROPORCIÓN DEL VALOR
# en mora logró recuperarse. Cruza dinero recuperado (pagos exitosos) contra el
# valor de las cuotas vencidas (saldo en mora). Responde: "de cada peso vencido,
# ¿cuánto volvió a caja?". Es la métrica que le importa a tesorería, no al robot.
def _metrica_eficiencia_cobranza():
    monto_en_mora = _scalar(
        "SELECT sum(cuota_mensual) FROM saldo WHERE estado ILIKE '%%mora%%'"
    ) or 0
    if not monto_en_mora:
        return dict(disponible=False, valor=None)

    monto_recuperado = _scalar(
        "SELECT sum(monto) FROM pagos WHERE estado ILIKE '%%exito%%'"
    ) or 0
    pagos_exitosos = _scalar(
        "SELECT count(*) FROM pagos WHERE estado ILIKE '%%exito%%'"
    ) or 0

    return dict(
        disponible=True, valor=_pct(float(monto_recuperado), float(monto_en_mora)),
        monto_recuperado=float(monto_recuperado), monto_en_mora=float(monto_en_mora),
        pagos_exitosos=pagos_exitosos,
    )


# ---------------------------------------------------------------------------
# Métrica 3 — Índice de salud de cartera ponderado
# ---------------------------------------------------------------------------
# Idea (no estándar): la "tasa de mora" clásica trata igual una cuota vencida
# hace 2 días que una vencida hace 3 meses. Aquí ponderamos cada saldo en mora
# por su ANTIGÜEDAD (días de vencimiento, tope 90): mientras más viejo, más pesa
# el deterioro. La salud = 100 − deterioro ponderado. Un mismo % de mora puede
# dar salud muy distinta según qué tan podrida esté. Es un semáforo de riesgo real.
def _metrica_salud_cartera():
    fila = _row(
        "SELECT "
        "  COALESCE(sum(saldo_total), 0), "
        "  COALESCE(sum(CASE WHEN estado ILIKE '%%mora%%' THEN saldo_total ELSE 0 END), 0), "
        "  COALESCE(sum(CASE WHEN estado ILIKE '%%mora%%' "
        "       THEN saldo_total * LEAST(GREATEST(CURRENT_DATE - fecha_vencimiento, 0), 90) / 90.0 "
        "       ELSE 0 END), 0), "
        "  COALESCE(round(avg(CASE WHEN estado ILIKE '%%mora%%' "
        "       THEN GREATEST(CURRENT_DATE - fecha_vencimiento, 0) END)), 0) "
        "FROM saldo"
    )
    total, mora_bruta, mora_ponderada, dias_prom = fila or (0, 0, 0, 0)
    total = float(total or 0)
    if not total:
        return dict(disponible=False, valor=None)

    deterioro = float(mora_ponderada or 0) / total * 100
    salud = round(100 - deterioro, 1)
    return dict(
        disponible=True, valor=salud,
        deterioro=round(deterioro, 1),
        mora_bruta=float(mora_bruta or 0), total=total,
        dias_prom=int(dias_prom or 0),
    )


def compute_metricas():
    """Devuelve la lista de las 3 métricas no estándar, lista para la plantilla."""
    m1 = _metrica_friccion()
    m2 = _metrica_eficiencia_cobranza()
    m3 = _metrica_salud_cartera()

    metricas = [
        {
            'num': 1,
            'nombre': 'Índice de fricción conversacional',
            'que_mide': 'Cuánto esfuerzo (mensajes) le cuesta al asociado llegar a la '
                        'respuesta. Menos es mejor.',
            'valor': m1['valor'],
            'unidad': 'msgs/conv.',
            'disponible': m1['disponible'],
            'icono': 'friccion',
            'estado': _estado(m1['valor'], naranja=4, rojo=6, mayor_es_peor=True),
            'umbral': 'Ideal ≤ 3 · alerta naranja > 4 · alerta roja > 6',
            'diseno': 'La IA cruzó volumen de turnos con repeticiones de texto: no mide '
                      'si el bot resuelve, sino cuánto esfuerzo le cuesta al asociado '
                      'llegar a la respuesta. Es el reverso de la auto-contención.',
            'formula': 'mensajes de usuario / conversaciones (+ reintentos por repetición de texto)',
            'detalle': (f"{m1['msgs_usuario']} mensajes de usuario en {m1['sesiones']} "
                        f"conversaciones · {m1['reintentos']} reintentos (texto repetido) "
                        f"en {m1['sesiones_con_reintento']} conversaciones")
                       if m1['disponible'] else '',
            'faltante': 'Aún no hay conversaciones registradas en n8n_chat_histories.',
        },
        {
            'num': 2,
            'nombre': 'Eficiencia de campaña de cobranza',
            'que_mide': 'De cada $100 vencidos, cuántos pesos realmente volvieron a caja. '
                        'Más alto es mejor.',
            'valor': m2['valor'],
            'unidad': '%',
            'disponible': m2['disponible'],
            'icono': 'cobranza',
            'estado': _estado(m2['valor'], naranja=40, rojo=20, mayor_es_peor=False),
            'umbral': 'Objetivo ≥ 40% del valor vencido · alerta roja < 20%',
            'diseno': 'La IA propuso medir dinero recuperado sobre valor en mora, no el '
                      'número de pagos. Un solo pago grande puede valer más que diez '
                      'pequeños: esta métrica lo captura en pesos, no en conteo.',
            'formula': 'Σ pagos exitosos ($) / Σ cuotas vencidas en mora ($) × 100',
            'detalle': (f"{_cop(m2['monto_recuperado'])} recuperados de "
                        f"{_cop(m2['monto_en_mora'])} en cuotas vencidas · "
                        f"{m2['pagos_exitosos']} pagos exitosos")
                       if m2['disponible'] else '',
            'faltante': 'No hay saldos en mora con cuota registrada para atribuir la campaña.',
        },
        {
            'num': 3,
            'nombre': 'Índice de salud de cartera ponderado',
            'que_mide': 'Nota de 0 a 100 de la cartera: castiga más las deudas más '
                        'viejas. Más alto = más sana.',
            'valor': m3['valor'],
            'unidad': 'pts (0–100)',
            'disponible': m3['disponible'],
            'icono': 'cartera',
            'estado': _estado(m3['valor'], naranja=85, rojo=70, mayor_es_peor=False),
            'umbral': 'Sano ≥ 85 · alerta naranja < 85 · alerta roja < 70',
            'diseno': 'La IA reemplazó la tasa de mora plana por un deterioro PONDERADO '
                      'por antigüedad: una cuota vencida hace 60 días pesa mucho más que '
                      'una de 5 días. Dos carteras con igual % de mora pueden tener salud '
                      'muy distinta según qué tan vieja sea.',
            'formula': '100 − [ Σ (saldo en mora × antigüedad/90) / Σ saldo total × 100 ]',
            'detalle': (f"Deterioro ponderado {m3['deterioro']}% · "
                        f"{_cop(m3['mora_bruta'])} en mora sobre {_cop(m3['total'])} de cartera · "
                        f"antigüedad media {m3['dias_prom']} días")
                       if m3['disponible'] else '',
            'faltante': 'La tabla saldo no tiene registros de cartera aún.',
        },
    ]

    con_datos = sum(1 for m in metricas if m['disponible'])
    en_alerta = sum(1 for m in metricas if m['estado'] in ('rojo', 'naranja'))
    resumen = dict(
        total=len(metricas),
        con_datos=con_datos,
        en_alerta=en_alerta,
        sin_datos=len(metricas) - con_datos,
    )
    return metricas, resumen
