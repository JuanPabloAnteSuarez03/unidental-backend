"""Helper para enviar mensajes de WhatsApp utilizando Twilio.

Este módulo encapsula la lógica de autenticación y envío para que
otras partes de la aplicación solo llamen a send_template() con el
número de destino, el SID de la plantilla de contenido y las
variables necesarias.
"""

import json
from typing import Dict

from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
import logging

logger = logging.getLogger(__name__)

# Instancia global del cliente Twilio (se crea una sola vez)
_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

DEFAULT_FROM = getattr(settings, "TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")


def send_template(to: str, content_sid: str, variables: Dict[str, str]) -> str:
    """Envía una plantilla (content SID) por WhatsApp.

    Args:
        to: Número de destino en formato internacional. Ej. "+57300..." (sin "whatsapp:" prefix).
        content_sid: SID de la plantilla de contenido aprobada en Twilio (HX...).
        variables: Diccionario con las variables de la plantilla. Las claves deben ser
                   strings "1", "2", ... según el orden definido en Twilio.

    Returns:
        str: SID del mensaje enviado (SM...).

    Raises:
        TwilioException: Si la API responde con error.
    """
    whatsapp_to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"

    try:
        message = _client.messages.create(
            from_=DEFAULT_FROM,
            content_sid=content_sid,
            content_variables=json.dumps(variables),
            to=whatsapp_to,
        )
        logger.info("WhatsApp enviado a %s (SID=%s)", whatsapp_to, message.sid)
        return message.sid
    except TwilioException as exc:
        logger.error("Error enviando WhatsApp a %s: %s", whatsapp_to, exc)
        raise 