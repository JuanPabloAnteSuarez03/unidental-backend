from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import Cashes, Movements, Transfers


@admin.register(Cashes)
class CashAdmin(admin.ModelAdmin):
    list_display = [
        'location_name', 'location_type', 'balance_formatted', 
        'is_active', 'created_at', 'movements_count'
    ]
    list_filter = ['is_active', 'location__type', 'created_at']
    search_fields = ['location__name', 'location__address']
    readonly_fields = ['balance', 'created_at', 'updated_at', 'movements_link']
    ordering = ['location__name']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('location', 'is_active')
        }),
        ('Saldo', {
            'fields': ('balance',),
            'description': 'El saldo se calcula automáticamente basado en los movimientos.'
        }),
        ('Movimientos', {
            'fields': ('movements_link',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def location_name(self, obj):
        return obj.location.name
    location_name.short_description = 'Ubicación'

    def location_type(self, obj):
        return obj.location.get_type_display()
    location_type.short_description = 'Tipo'

    def balance_formatted(self, obj):
        color = 'green' if obj.balance >= 0 else 'red'
        formatted_amount = f"${obj.balance:,.2f}"
        return format_html(
            '<span style="color: {};">{}</span>',
            color, formatted_amount
        )
    balance_formatted.short_description = 'Saldo'

    def movements_count(self, obj):
        count = obj.movements.count()
        if count > 0:
            url = reverse('admin:cash_movements_changelist') + f'?cash__id__exact={obj.id}'
            return format_html('<a href="{}">{} movimientos</a>', url, count)
        return '0 movimientos'
    movements_count.short_description = 'Movimientos'

    def movements_link(self, obj):
        if obj.pk:
            url = reverse('admin:cash_movements_changelist') + f'?cash__id__exact={obj.id}'
            return format_html('<a href="{}" target="_blank">Ver movimientos de esta caja</a>', url)
        return 'Guarde primero para ver movimientos'
    movements_link.short_description = 'Movimientos'

    actions = ['recalculate_balance', 'activate_cash', 'deactivate_cash']

    def recalculate_balance(self, request, queryset):
        for cash in queryset:
            cash.update_balance()
        self.message_user(request, f'Saldo recalculado para {queryset.count()} cajas.')
    recalculate_balance.short_description = 'Recalcular saldo'

    def activate_cash(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} cajas activadas.')
    activate_cash.short_description = 'Activar cajas seleccionadas'

    def deactivate_cash(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} cajas desactivadas.')
    deactivate_cash.short_description = 'Desactivar cajas seleccionadas'


@admin.register(Movements)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'cash_location', 'movement_type', 'amount_formatted', 
        'reference_type', 'status', 'created_by', 'created_at'
    ]
    list_filter = [
        'movement_type', 'reference_type', 'status', 'created_at',
        'cash__location__type', 'cash__location__name'
    ]
    search_fields = [
        'notes', 'cash__location__name', 'created_by__username',
        'sale__id', 'purchase_order__id'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'cancelled_at',
        'related_sale_link', 'related_purchase_link'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Información del Movimiento', {
            'fields': ('cash', 'movement_type', 'amount', 'reference_type', 'notes')
        }),
        ('Estado', {
            'fields': ('status', 'cancelled_by', 'cancelled_at', 'cancellation_reason')
        }),
        ('Referencias', {
            'fields': ('sale', 'purchase_order', 'related_sale_link', 'related_purchase_link'),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def cash_location(self, obj):
        return f"{obj.cash.location.name}"
    cash_location.short_description = 'Caja'

    def amount_formatted(self, obj):
        if obj.movement_type == 'egreso':
            formatted_amount = f"-${obj.amount:,.2f}"
            return format_html('<span style="color: red;">{}</span>', formatted_amount)
        elif obj.movement_type == 'ingreso':
            formatted_amount = f"+${obj.amount:,.2f}"
            return format_html('<span style="color: green;">{}</span>', formatted_amount)
        else:  # ajuste
            formatted_amount = f"${obj.amount:,.2f}"
            return format_html('<span style="color: blue;">{}</span>', formatted_amount)
    amount_formatted.short_description = 'Monto'

    def related_sale_link(self, obj):
        if obj.sale:
            url = reverse('admin:sales_sale_change', args=[obj.sale.id])
            return format_html('<a href="{}" target="_blank">Venta #{}</a>', url, obj.sale.id)
        return 'No relacionada'
    related_sale_link.short_description = 'Venta Relacionada'

    def related_purchase_link(self, obj):
        if obj.purchase_order:
            url = reverse('admin:purchases_purchaseorder_change', args=[obj.purchase_order.id])
            return format_html('<a href="{}" target="_blank">Orden #{}</a>', url, obj.purchase_order.id)
        return 'No relacionada'
    related_purchase_link.short_description = 'Orden de Compra Relacionada'

    actions = ['cancel_movements', 'reactivate_movements']

    def cancel_movements(self, request, queryset):
        active_movements = queryset.filter(status='active')
        cancelled_count = 0
        for movement in active_movements:
            try:
                movement.cancel(request.user, "Cancelado desde admin")
                cancelled_count += 1
            except Exception as e:
                self.message_user(request, f'Error al cancelar movimiento {movement.id}: {e}', level='ERROR')
        
        if cancelled_count > 0:
            self.message_user(request, f'{cancelled_count} movimientos cancelados.')
    cancel_movements.short_description = 'Cancelar movimientos seleccionados'

    def reactivate_movements(self, request, queryset):
        cancelled_movements = queryset.filter(status='cancelled')
        reactivated_count = 0
        for movement in cancelled_movements:
            try:
                movement.reactivate(request.user)
                reactivated_count += 1
            except Exception as e:
                self.message_user(request, f'Error al reactivar movimiento {movement.id}: {e}', level='ERROR')
        
        if reactivated_count > 0:
            self.message_user(request, f'{reactivated_count} movimientos reactivados.')
    reactivate_movements.short_description = 'Reactivar movimientos seleccionados'


@admin.register(Transfers)
class CashTransferAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'origin_location', 'destination_location', 'amount_formatted',
        'status', 'created_by', 'created_at', 'completed_at'
    ]
    list_filter = ['status', 'created_at', 'completed_at']
    search_fields = [
        'notes', 'origin_cash__location__name', 'destination_cash__location__name',
        'created_by__username'
    ]
    readonly_fields = [
        'origin_movement_link', 'destination_movement_link',
        'created_at', 'completed_at'
    ]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Información de la Transferencia', {
            'fields': ('origin_cash', 'destination_cash', 'amount', 'notes')
        }),
        ('Estado', {
            'fields': ('status', 'completed_at')
        }),
        ('Movimientos Generados', {
            'fields': ('origin_movement', 'destination_movement', 'origin_movement_link', 'destination_movement_link'),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def origin_location(self, obj):
        return obj.origin_cash.location.name
    origin_location.short_description = 'Origen'

    def destination_location(self, obj):
        return obj.destination_cash.location.name
    destination_location.short_description = 'Destino'

    def amount_formatted(self, obj):
        formatted_amount = f"${obj.amount:,.2f}"
        return format_html('{}', formatted_amount)
    amount_formatted.short_description = 'Monto'

    def origin_movement_link(self, obj):
        if obj.origin_movement:
            url = reverse('admin:cash_movements_change', args=[obj.origin_movement.id])
            return format_html('<a href="{}" target="_blank">Movimiento #{}</a>', url, obj.origin_movement.id)
        return 'No creado'
    origin_movement_link.short_description = 'Movimiento de Salida'

    def destination_movement_link(self, obj):
        if obj.destination_movement:
            url = reverse('admin:cash_movements_change', args=[obj.destination_movement.id])
            return format_html('<a href="{}" target="_blank">Movimiento #{}</a>', url, obj.destination_movement.id)
        return 'No creado'
    destination_movement_link.short_description = 'Movimiento de Entrada'

    actions = ['execute_transfers', 'cancel_transfers']

    def execute_transfers(self, request, queryset):
        pending_transfers = queryset.filter(status='pending')
        executed_count = 0
        for transfer in pending_transfers:
            try:
                transfer.execute_transfer(request.user)
                executed_count += 1
            except Exception as e:
                self.message_user(request, f'Error al ejecutar transferencia {transfer.id}: {e}', level='ERROR')
        
        if executed_count > 0:
            self.message_user(request, f'{executed_count} transferencias ejecutadas.')
    execute_transfers.short_description = 'Ejecutar transferencias pendientes'

    def cancel_transfers(self, request, queryset):
        active_transfers = queryset.exclude(status='cancelled')
        cancelled_count = 0
        for transfer in active_transfers:
            try:
                transfer.cancel_transfer(request.user, "Cancelado desde admin")
                cancelled_count += 1
            except Exception as e:
                self.message_user(request, f'Error al cancelar transferencia {transfer.id}: {e}', level='ERROR')
        
        if cancelled_count > 0:
            self.message_user(request, f'{cancelled_count} transferencias canceladas.')
    cancel_transfers.short_description = 'Cancelar transferencias seleccionadas'
