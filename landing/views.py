import json
import uuid

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from . import n8n_client
from . import kpis as kpis_service


def home(request):
    return render(request, 'landing/home.html')


def agent_dashboard(request):
    return render(request, 'landing/agent-dashboard.html')


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
