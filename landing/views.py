import json
import uuid

from django.db import connection, DatabaseError
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from . import n8n_client
from . import kpis as kpis_service


def home(request):
    return render(request, 'landing/home.html')


def agent_dashboard(request):
    return render(request, 'landing/agent-dashboard.html')


def pago(request):
    """
    Pasarela de pago simulada. Página de pruebas que recibe los datos del pago
    por parámetros GET y los muestra para confirmación. Al confirmar/cancelar,
    el navegador hace POST a `pago_registrar` (mismo origen). Toda la lógica de
    presentación vive en el template.
    """
    return render(request, 'landing/pago.html')


# Estado que se guarda en la tabla `pagos` según el resultado de la pasarela.
# 'exitoso' se alinea con los KPIs (que filtran estado ILIKE '%exito%').
_ESTADO_PAGO = {'aprobado': 'exitoso', 'rechazado': 'rechazado'}


def _registrar_pago(datos):
    """
    Inserta el pago en la tabla `pagos` de Supabase. Es idempotente por
    `numero_transaccion` (la referencia): si ya existe, no duplica. Devuelve
    True si la fila queda registrada (recién insertada o ya existente).
    """
    referencia = datos['referencia']
    cedula = (datos.get('cedula') or '').strip()
    id_cliente = int(cedula) if cedula.isdigit() else None

    with connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pagos WHERE numero_transaccion = %s LIMIT 1",
            [referencia],
        )
        if cur.fetchone():
            return True  # ya registrado (reintento): no duplicar

        cur.execute(
            "INSERT INTO pagos "
            "(chat_id, id_cliente, monto, tipo_pago, numero_transaccion, "
            " estado, medio_comprobante, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, now())",
            [
                datos['chat_id'],
                id_cliente,
                datos['monto'],
                datos.get('concepto') or 'Pago',
                referencia,
                datos['estado'],
                datos.get('canal') or 'web',
            ],
        )
    return True


@csrf_exempt
@require_POST
def pago_registrar(request):
    """
    Registra el resultado de un pago simulado: lo guarda en la tabla `pagos`
    de Supabase y lo reenvía al callback_url de n8n. El navegador de la
    pasarela le pega aquí (mismo origen, sin CORS). Responde {ok} siempre en
    JSON; ante fallo devuelve un mensaje para que la pasarela reintente.
    """
    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Solicitud inválida.'}, status=400)

    chat_id      = (body.get('chat_id') or '').strip()
    referencia   = (body.get('referencia') or '').strip()
    callback_url = (body.get('callback_url') or '').strip()
    estado_in    = (body.get('estado') or '').strip().lower()

    if not (chat_id and referencia and estado_in in _ESTADO_PAGO):
        return JsonResponse(
            {'ok': False, 'error': 'Faltan datos obligatorios del pago.'},
            status=400,
        )

    try:
        monto = float(body.get('monto'))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Monto inválido.'}, status=400)

    datos = {
        'chat_id':    chat_id,
        'cedula':     body.get('cedula'),
        'monto':      monto,
        'concepto':   body.get('concepto'),
        'referencia': referencia,
        'canal':      body.get('canal'),
        'estado':     _ESTADO_PAGO[estado_in],
    }

    # 1) Registrar en Supabase (requisito: todo pago queda en la tabla `pagos`).
    try:
        _registrar_pago(datos)
    except (DatabaseError, ValueError):
        return JsonResponse(
            {'ok': False, 'error': 'No se pudo registrar el pago. Reintenta.'},
            status=502,
        )

    # 2) Notificar el resultado al flujo de n8n (para que continúe la conversación).
    #    Si el callback falla, el pago YA quedó registrado; se avisa como no crítico.
    callback_ok = True
    if callback_url:
        payload = {
            'chat_id':    chat_id,
            'referencia': referencia,
            'estado':     estado_in,          # 'aprobado' / 'rechazado' (contrato de n8n)
            'monto':      monto,
            'cedula':     datos['cedula'],
            'canal':      datos['canal'],
        }
        try:
            n8n_client.forward_to(callback_url, payload)
        except n8n_client.N8nError:
            callback_ok = False

    return JsonResponse({'ok': True, 'estado': estado_in, 'callback_ok': callback_ok})


def kpi_dashboard(request):
    """Dashboard ejecutivo con los 6 KPIs calculados desde Supabase."""
    kpis, mora = kpis_service.compute_kpis()
    con_datos = sum(1 for k in kpis if k['disponible'])
    en_alerta = sum(1 for k in kpis if k['estado'] in ('rojo', 'naranja'))
    return render(request, 'landing/kpi-dashboard.html', {
        'kpis': kpis,
        'mora': mora,
        'con_datos': con_datos,
        'total_kpis': len(kpis),
        'en_alerta': en_alerta,
        'sin_datos': len(kpis) - con_datos,
    })


# Límites de tamaño (sobre el contenido ya decodificado)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {'image/jpeg', 'image/png', 'image/webp'}


def _get_chat_id(request):
    """chat_id estable por sesión de navegador; lo administra Django, no el JS."""
    chat_id = request.session.get('chat_id')
    if not chat_id:
        chat_id = 'web-' + uuid.uuid4().hex[:8]
        request.session['chat_id'] = chat_id
    return chat_id


def _clean_b64(value: str) -> str:
    """Quita, por si acaso, el prefijo 'data:...;base64,' que a veces llega del navegador."""
    value = (value or '').strip()
    if value.startswith('data:'):
        comma = value.find(',')
        if comma != -1:
            value = value[comma + 1:]
    return value


def _b64_size(b64: str) -> int:
    """Tamaño aproximado en bytes del contenido decodificado, sin decodificar."""
    return (len(b64) * 3) // 4 - b64.count('=')


@require_POST
def chat_api(request):
    """
    Proxy del chat hacia n8n. Una sola modalidad por request:
      - Texto : {mensaje}          (la ubicación llega como texto por aquí)
      - Audio : {audio}            (base64 sin prefijo data:)
      - Imagen: {imagen, formato}  (base64 sin prefijo; formato = MIME)

    El chat_id se toma de la sesión (no del JS). Responde siempre {respuesta}.
    """
    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'respuesta': 'Solicitud inválida.'}, status=400)

    chat_id = _get_chat_id(request)

    try:
        payload = _build_payload(chat_id, body)
    except ValueError as exc:
        return JsonResponse({'respuesta': str(exc)}, status=400)

    try:
        data = n8n_client.forward(payload)
    except n8n_client.N8nError:
        return JsonResponse(
            {'respuesta': 'Tuve un problema para conectarme. Inténtalo en un momento. 🙏'},
            status=502,
        )

    return JsonResponse({'respuesta': n8n_client.extract_reply(data)})


@require_POST
def chat_reset(request):
    """
    Inicia una conversación nueva: descarta el chat_id de la sesión para que el
    próximo mensaje genere uno fresco (n8n lo usa como clave de memoria, así que
    un chat_id nuevo = conversación desde cero).
    """
    request.session.pop('chat_id', None)
    return JsonResponse({'ok': True})


def _build_payload(chat_id, body):
    """Valida el cuerpo y arma el payload para n8n. Exige una sola modalidad."""
    audio   = _clean_b64(body.get('audio'))
    imagen  = _clean_b64(body.get('imagen'))
    mensaje = (body.get('mensaje') or '').strip()

    if sum(bool(x) for x in (audio, imagen, mensaje)) != 1:
        raise ValueError('Envía exactamente una modalidad: texto, audio o imagen.')

    if audio:
        if _b64_size(audio) > MAX_AUDIO_BYTES:
            raise ValueError('El audio supera el tamaño máximo de 10 MB.')
        return {'chat_id': chat_id, 'audio': audio}

    if imagen:
        formato = (body.get('formato') or '').strip().lower()
        if formato not in ALLOWED_IMAGE_FORMATS:
            raise ValueError('Formato no admitido. Usa JPG o PNG.')
        if _b64_size(imagen) > MAX_IMAGE_BYTES:
            raise ValueError('La imagen supera el tamaño máximo de 5 MB.')
        return {'chat_id': chat_id, 'imagen': imagen, 'formato': formato}

    return {'chat_id': chat_id, 'mensaje': mensaje}
