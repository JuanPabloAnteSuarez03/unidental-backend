from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from credits.models import CreditPurchaseReminder
from core.whatsapp import send_template
from twilio.base.exceptions import TwilioException
import logging
import json

logger = logging.getLogger(__name__)

# Mapear tipos de recordatorio a SID de plantilla (configurable en settings)
TEMPLATE_SIDS = {
    'upcoming': getattr(settings, 'TWILIO_TEMPLATE_UPCOMING', None),
    'overdue': getattr(settings, 'TWILIO_TEMPLATE_OVERDUE', None),
    'balance_ok': getattr(settings, 'TWILIO_TEMPLATE_BALANCE_OK', None),
    'payment_received': getattr(settings, 'TWILIO_TEMPLATE_PAYMENT_RECEIVED', None),
}

class Command(BaseCommand):
    help = "Envía recordatorios de pago de compras a crédito que estén pendientes."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo muestra los recordatorios que se enviarían, sin enviar nada')

    def handle(self, *args, **options):
        now = timezone.now()
        dry_run = options['dry_run']

        pending_qs = CreditPurchaseReminder.objects.filter(status='pending', scheduled_date__lte=now)
        total = pending_qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No hay recordatorios pendientes.'))
            return

        self.stdout.write(f"Encontrados {total} recordatorios a procesar (dry_run={dry_run}).")

        for reminder in pending_qs.select_related('credit_account__purchase_order__supplier'):
            supplier = reminder.credit_account.purchase_order.supplier
            phone = supplier.phone
            if not phone:
                self.stderr.write(self.style.WARNING(f"Proveedor {supplier.name} sin teléfono. Marcando como fallido."))
                reminder.status = 'failed'
                reminder.error_message = 'Proveedor sin número de teléfono.'
                reminder.save(update_fields=['status', 'error_message'])
                continue

            template_sid = TEMPLATE_SIDS.get(reminder.reminder_type)
            variables = {}
            if reminder.reminder_type in ('upcoming', 'overdue'):
                variables = {
                    "1": supplier.name,
                    "2": str(reminder.credit_account.payment_amount or reminder.credit_account.remaining_amount),
                    "3": str(reminder.credit_account.next_payment_date),
                }

            try:
                if dry_run:
                    self.stdout.write(f"[DRY] Enviar {reminder.reminder_type} a {phone} usando plantilla {template_sid or 'text'}")
                else:
                    if template_sid:
                        sid = send_template(phone, template_sid, variables)
                    else:
                        # Fallback: usa send_template con Content SID del propio reminder.message_content si es SID
                        sid = send_template(phone, template_sid or settings.TWILIO_TEMPLATE_OVERDUE or "", variables)
                    reminder.status = 'sent'
                    reminder.sent_date = now
                    reminder.whatsapp_message_id = sid
                    reminder.save(update_fields=['status', 'sent_date', 'whatsapp_message_id'])
                    self.stdout.write(self.style.SUCCESS(f"Enviado → {phone}"))
            except TwilioException as exc:
                reminder.status = 'failed'
                reminder.error_message = str(exc)
                reminder.retry_count += 1
                reminder.save(update_fields=['status', 'error_message', 'retry_count'])
                self.stderr.write(self.style.ERROR(f"Fallo ({phone}): {exc}")) 