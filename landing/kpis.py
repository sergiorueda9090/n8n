"""
Cálculo de los 6 KPIs ejecutivos del dashboard de Aurora Financiera.

Cada KPI se calcula con SQL crudo directamente sobre la base de datos
(Supabase/PostgreSQL en producción). La filosofía es NO inventar cifras:
si la tabla que alimenta un KPI todavía está vacía, el KPI se marca como
`disponible=False` y el dashboard muestra "Sin datos aún" con lo que hace
falta para poder calcularlo, en vez de mostrar un número falso.

Estado de alerta (`estado`) de cada KPI:
    'ok'        → dentro del objetivo (verde)
    'naranja'   → alerta naranja
    'rojo'      → alerta roja
    'sin_datos' → aún no hay datos para calcularlo (gris)

`compute_kpis()` devuelve una lista de dicts lista para la plantilla.
"""
from django.db import connection


def _scalar(sql, params=None):
    """Ejecuta una consulta que devuelve un único valor. None si no hay filas."""
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def _pct(numerador, denominador):
    """Porcentaje seguro (evita división por cero). Devuelve float redondeado."""
    if not denominador:
        return 0.0
    return round(numerador / denominador * 100, 1)


# Frases que, dichas por el asistente o el flujo, indican que la conversación
# se derivó a un agente humano (escalamiento). Heurística sobre el contenido
# del chat mientras no exista un evento explícito de escalamiento.
_FRASES_ESCALAMIENTO = [
    '%te comunico con%',
    '%comunicar con un asesor%',
    '%transferir%asesor%',
    '%agente humano%',
    '%asesor humano%',
    '%un asesor te%',
    '%línea de atención%',
    '%te contactará un asesor%',
]


# ---------------------------------------------------------------------------
# KPI 1 — Tasa de auto-contención
# ---------------------------------------------------------------------------
def _kpi_autocontencion():
    total = _scalar("SELECT count(DISTINCT session_id) FROM n8n_chat_histories") or 0
    if not total:
        return dict(disponible=False, valor=None, numerador=0, denominador=0,
                    escaladas=0, contenidas=0)

    escaladas = _scalar(
        "SELECT count(DISTINCT session_id) FROM n8n_chat_histories "
        "WHERE message->>'content' ILIKE ANY(%s)",
        [_FRASES_ESCALAMIENTO],
    ) or 0
    contenidas = total - escaladas
    return dict(disponible=True, valor=_pct(contenidas, total),
                numerador=contenidas, denominador=total, escaladas=escaladas,
                contenidas=contenidas)


# ---------------------------------------------------------------------------
# KPI 5 — Tasa de abandono de onboarding digital
# ---------------------------------------------------------------------------
def _kpi_abandono_onboarding():
    total = _scalar("SELECT count(*) FROM onboarding") or 0
    completados = _scalar(
        "SELECT count(*) FROM onboarding "
        "WHERE resultado ILIKE '%%exito%%' OR resultado ILIKE '%%vinculacion_exitosa%%'"
    ) or 0
    # Flujos que empezaron a subir documentos pero quedaron a medias (no llegaron
    # a crear registro de onboarding): cuentan como iniciados NO completados.
    en_curso = _scalar(
        "SELECT count(*) FROM extracciones_temp "
        "WHERE estado NOT IN ('completado', 'finalizado', 'exitoso')"
    ) or 0

    iniciados = total + en_curso
    if not iniciados:
        return dict(disponible=False, valor=None, iniciados=0, completados=0,
                    abandonados=0, en_curso=0)
    abandonados = (total - completados) + en_curso
    return dict(disponible=True, valor=_pct(abandonados, iniciados),
                iniciados=iniciados, completados=completados,
                abandonados=abandonados, en_curso=en_curso)


# ---------------------------------------------------------------------------
# KPI 6 — Recuperación de mora temprana (1–30 días)
# ---------------------------------------------------------------------------
def _kpi_recuperacion_mora():
    en_mora_temprana = _scalar(
        "SELECT count(*) FROM saldo "
        "WHERE estado ILIKE '%%mora%%' "
        "AND (CURRENT_DATE - fecha_vencimiento) BETWEEN 1 AND 30"
    ) or 0
    if not en_mora_temprana:
        return dict(disponible=False, valor=None, contactados=0, pagaron=0)

    pagaron = _scalar(
        "SELECT count(DISTINCT s.id_cliente) FROM saldo s "
        "JOIN pagos p ON p.id_cliente = s.id_cliente "
        "WHERE s.estado ILIKE '%%mora%%' "
        "AND (CURRENT_DATE - s.fecha_vencimiento) BETWEEN 1 AND 30 "
        "AND p.estado ILIKE '%%exito%%'"
    ) or 0
    return dict(disponible=True, valor=_pct(pagaron, en_mora_temprana),
                contactados=en_mora_temprana, pagaron=pagaron)


# ---------------------------------------------------------------------------
# Indicador de negocio — Tasa de mora general (no es KPI operativo diario)
# ---------------------------------------------------------------------------
def _indicador_mora_general():
    total = _scalar("SELECT count(*) FROM saldo") or 0
    en_mora = _scalar("SELECT count(*) FROM saldo WHERE estado ILIKE '%%mora%%'") or 0
    return dict(disponible=bool(total), valor=_pct(en_mora, total),
                en_mora=en_mora, total=total)


def _estado(valor, *, rojo=None, naranja=None, mayor_es_peor=True):
    """
    Devuelve 'rojo' / 'naranja' / 'ok' comparando `valor` contra umbrales.
    `mayor_es_peor=True`  → un valor ALTO dispara alerta (ej. % de abandono).
    `mayor_es_peor=False` → un valor BAJO dispara alerta (ej. % de contención).
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


def compute_kpis():
    """Devuelve (lista_de_kpis, indicador_mora_general) para la plantilla."""
    k1 = _kpi_autocontencion()
    k5 = _kpi_abandono_onboarding()
    k6 = _kpi_recuperacion_mora()
    mora = _indicador_mora_general()

    kpis = [
        {
            'num': 1,
            'nombre': 'Tasa de auto-contención',
            'valor': k1['valor'],
            'unidad': '%',
            'disponible': k1['disponible'],
            'formula': '(conversaciones totales − escaladas) / conversaciones totales × 100',
            'umbral': 'Alerta roja si baja de 60%',
            'estado': _estado(k1['valor'], rojo=60, mayor_es_peor=False),
            'por_que': 'Mide la promesa del comité de reducir 50% la carga del call '
                       'center humano en 6 meses. Línea base: 0% (no existía autoservicio).',
            'detalle': (f"{k1['contenidas']} resueltas por el bot de "
                        f"{k1['denominador']} conversaciones · {k1['escaladas']} escaladas a humano")
                       if k1['disponible'] else '',
            'faltante': '',
            'icono': 'robot',
        },
        {
            'num': 2,
            'nombre': 'Tiempo de 1ª respuesta (agente humano)',
            'valor': None,
            'unidad': 'min',
            'disponible': False,
            'formula': 'Σ tiempos de primera respuesta / total de tickets escalados',
            'umbral': 'Alerta naranja si supera 3 min',
            'estado': 'sin_datos',
            'por_que': 'Sigue el dolor más visible hoy: 12 min de espera promedio vs. '
                       '≤ 3 min de referencia del sector.',
            'detalle': '',
            'faltante': 'Requiere registrar la hora de escalamiento y la hora de la '
                        'primera respuesta del agente (tabla de tickets con timestamps).',
            'icono': 'reloj',
        },
        {
            'num': 3,
            'nombre': 'Conversión de campañas de cobranza',
            'valor': None,
            'unidad': '%',
            'disponible': False,
            'formula': 'pagos generados / mensajes enviados, por oleada × 100',
            'umbral': 'Alerta roja si baja de 5%',
            'estado': 'sin_datos',
            'por_que': 'Mide si la cobranza preventiva convierte el contacto en pago.',
            'detalle': '',
            'faltante': 'Requiere datos de campañas (mensajes enviados por oleada) y '
                        'pagos asociados. La tabla "pagos" aún está vacía.',
            'icono': 'megafono',
        },
        {
            'num': 4,
            'nombre': 'NPS Aurora (global)',
            'valor': None,
            'unidad': 'pts',
            'disponible': False,
            'formula': '% promotores (9–10) − % detractores (0–6)',
            'umbral': 'Alerta naranja si cae bajo 40 o no mejora mes a mes',
            'estado': 'sin_datos',
            'por_que': 'Mide el compromiso del comité de subir el NPS mínimo 15 puntos '
                       '(32 → 47+) en 6 meses.',
            'detalle': '',
            'faltante': 'Requiere una encuesta de satisfacción (¿qué tan probable es que '
                        'recomiendes Aurora?) al cierre de interacciones clave.',
            'icono': 'estrella',
        },
        {
            'num': 5,
            'nombre': 'Abandono de onboarding digital',
            'valor': k5['valor'],
            'unidad': '%',
            'disponible': k5['disponible'],
            'formula': 'flujos iniciados sin completar / total iniciados × 100',
            'umbral': 'Alerta roja si supera 15%',
            'estado': _estado(k5['valor'], rojo=15, mayor_es_peor=True),
            'por_que': 'Ataca el 28% de abandono del proceso presencial con documentos físicos.',
            'detalle': (f"{k5['abandonados']} sin completar de {k5['iniciados']} iniciados · "
                        f"{k5['completados']} vinculaciones exitosas · {k5['en_curso']} a medias")
                       if k5['disponible'] else '',
            'faltante': '',
            'icono': 'documento',
        },
        {
            'num': 6,
            'nombre': 'Recuperación de mora temprana',
            'valor': k6['valor'],
            'unidad': '%',
            'disponible': k6['disponible'],
            'formula': 'asociados 1–30 días que pagaron tras campaña / total contactados × 100',
            'umbral': 'Alerta naranja si baja de 30%',
            'estado': _estado(k6['valor'], naranja=30, mayor_es_peor=False),
            'por_que': 'Mide si la cobranza preventiva mueve la mora de consumo del 18% '
                       'actual hacia el 9% de referencia del sector.',
            'detalle': (f"{k6['pagaron']} pagaron de {k6['contactados']} en mora temprana (1–30 días)")
                       if k6['disponible'] else '',
            'faltante': ('Hay asociados en mora temprana, pero la tabla "pagos" está vacía: '
                         'aún no hay pagos que atribuir a la campaña.')
                        if not k6['disponible'] else '',
            'icono': 'billete',
        },
    ]
    return kpis, mora
