"""
Cliente ligero para reenviar peticiones del chat "Aurorita" al webhook de n8n.

Usa solo la librería estándar (urllib) para no añadir dependencias.
Todo se envía como application/json. La web manda una sola modalidad por
petición y el proxy le añade el chat_id de la sesión antes de reenviar:

  - Texto  -> {chat_id, mensaje}
  - Audio  -> {chat_id, audio, formato}      (audio en base64, sin prefijo data:)
  - Imagen -> {chat_id, imagen, formato}     (imagen en base64, sin prefijo data:)

n8n responde con {respuesta} (con fallbacks tolerantes en extract_reply).
"""
import json
import urllib.request
import urllib.error

from django.conf import settings


class N8nError(Exception):
    """Error al comunicarse con n8n (timeout, conexión, status != 2xx)."""


def _post(data: bytes, content_type: str) -> dict:
    """POST crudo al webhook de n8n. Devuelve el JSON de respuesta como dict."""
    req = urllib.request.Request(
        settings.N8N_WEBHOOK_URL,
        data=data,
        headers={'Content-Type': content_type},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.N8N_TIMEOUT) as resp:
            raw = resp.read().decode('utf-8').strip()
    except urllib.error.HTTPError as exc:
        raise N8nError(f'n8n respondió {exc.code}: {exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise N8nError(f'No se pudo conectar con n8n: {exc.reason}') from exc
    except TimeoutError as exc:
        raise N8nError('n8n no respondió a tiempo (timeout).') from exc

    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # n8n puede devolver texto plano; lo envolvemos.
        return {'respuesta': raw}
    # n8n a veces devuelve una lista [{...}]; tomamos el primer elemento.
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}
    return parsed if isinstance(parsed, dict) else {'respuesta': str(parsed)}


def forward(payload: dict) -> dict:
    """Reenvía el payload (ya con chat_id) a n8n como application/json."""
    data = json.dumps(payload).encode('utf-8')
    return _post(data, 'application/json')


def extract_reply(data: dict) -> str:
    """
    Extrae el texto de respuesta del bot de forma tolerante.
    Contrato preferido: {"respuesta": "..."}; con fallbacks habituales de n8n.
    """
    for key in ('respuesta', 'output', 'mensaje', 'text', 'reply', 'message'):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return 'Disculpa, no recibí una respuesta. ¿Puedes intentarlo de nuevo?'
