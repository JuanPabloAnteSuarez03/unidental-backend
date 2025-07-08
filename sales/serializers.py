from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from .models import Customer, Sale, SaleItem, Return, ReturnItem
from catalogs.models import Product, ProductBatch, ProductComponent
from catalogs.serializers import ProductSerializer, ProductSummarySerializer, ProductBatchSerializer
from inventory.models import InventoryStock, InventoryMovement, Location
from inventory.serializers import LocationSerializer
from django.db import models
from django.db import transaction
from decimal import Decimal


class CustomerSerializer(serializers.ModelSerializer):
    """Serializador para el modelo de Cliente."""
    
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'email', 'address', 'birthday', 'emergency_contact', 'notes', 'created_at']
        read_only_fields = ['created_at']


class SaleItemSerializer(serializers.ModelSerializer):
    """Serializador para los items de venta con soporte para lotes y productos compuestos."""
    
    product_details = ProductSerializer(source='product', read_only=True)
    batch_details = ProductBatchSerializer(source='batch', read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_details', 'batch', 'batch_details', 'quantity', 'unit_price', 'subtotal']

    def get_subtotal(self, obj):
        """Calcula el subtotal del item multiplicando cantidad por precio unitario."""
        return obj.quantity * obj.unit_price

    def validate(self, data):
        """Validaciones del item de venta con lotes."""
        quantity = data.get('quantity')
        product = data.get('product')
        batch = data.get('batch')
        
        if quantity and quantity <= 0:
            raise serializers.ValidationError({
                'quantity': 'La cantidad debe ser mayor a cero'
            })
        
        # Validar que si el producto no requiere control de lotes, no se especifique un lote
        if product and not product.requires_batch_control and batch:
            raise serializers.ValidationError({
                'batch': 'Este producto no requiere control de lotes.'
            })
        
        # Validar que si el producto requiere control de lotes, se especifique un lote
        if product and product.requires_batch_control and not batch:
            raise serializers.ValidationError({
                'batch': 'Este producto requiere especificar un lote.'
            })
        
        # Validar que el batch corresponde al producto (solo si se especifica un lote)
        if batch and product and batch.product != product:
            raise serializers.ValidationError({
                'batch': 'El lote no corresponde al producto seleccionado.'
            })
        
        return data


class SaleSerializer(serializers.ModelSerializer):
    """Serializador para las ventas con soporte para items anidados y productos compuestos."""
    
    items = SaleItemSerializer(many=True)
    confirm_breakdown = serializers.BooleanField(
        default=False,
        write_only=True,
        help_text="Si se envía en true, el sistema procederá a desarmar cajas/kits automáticamente según el plan sugerido."
    )
    customer_details = CustomerSerializer(source='customer', read_only=True)
    location_details = LocationSerializer(source='location', read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'customer', 'customer_details', 'location', 'location_details',
            'sale_date', 'sale_type', 'should_invoice', 'total_gross', 'total_net', 'items', 'confirm_breakdown'
        ]
        read_only_fields = ['sale_date', 'total_gross', 'total_net']

    @transaction.atomic
    def create(self, validated_data):
        """
        Crea una venta con sus items asociados.
        Actualiza automáticamente el stock de los productos usando la sede especificada.
        Maneja productos compuestos/kits y sus componentes inteligentemente.
        """
        items_data = validated_data.pop('items')
        # Señal de confirmación para desarmar composiciones
        confirm_breakdown = validated_data.pop('confirm_breakdown', False)
        # Almacenar en la instancia para que los métodos internos puedan consultarlo
        self._confirm_breakdown = confirm_breakdown
        sale = Sale.objects.create(**validated_data)
        sale_location = sale.location

        for item_data in items_data:
            product = item_data['product']
            batch = item_data.get('batch')
            quantity = item_data['quantity']
            
            # Procesar según el tipo de producto
            if product.is_composite():
                # Venta de producto compuesto (kit/caja)
                self._process_composite_sale(product, batch, quantity, sale, sale_location)
            elif product.is_component():
                # Venta de componente individual
                self._process_component_sale(product, batch, quantity, sale, sale_location)
            else:
                # Venta de producto simple
                self._process_simple_sale(product, batch, quantity, sale, sale_location)
            
            # Crear el item de venta
            SaleItem.objects.create(sale=sale, **item_data)

        return sale

    def _check_and_reserve_stock(self, product, batch, quantity, location):
        """Verifica y reserva stock para un producto específico."""
        if product.requires_batch_control:
            if not batch:
                raise serializers.ValidationError({
                    'items': f'El producto {product.name} requiere especificar un lote.'
                })
            
            try:
                stock_location = InventoryStock.objects.get(
                    product=product, 
                    location=location,
                    batch=batch
                )
                
                if stock_location.quantity < quantity:
                    raise serializers.ValidationError({
                        'items': f'Stock insuficiente del lote {batch.batch_number} del producto {product.name} en {location.name}. '
                                f'Disponible: {stock_location.quantity}, Solicitado: {quantity}'
                    })
                
            except InventoryStock.DoesNotExist:
                raise serializers.ValidationError({
                    'items': f'No hay stock del lote {batch.batch_number} del producto {product.name} en {location.name}'
                })
        else:
            try:
                stock_location = InventoryStock.objects.get(
                    product=product,
                    location=location,
                    batch__isnull=True
                )
                
                if stock_location.quantity < quantity:
                    raise serializers.ValidationError({
                        'items': f'Stock insuficiente del producto {product.name} en {location.name}. '
                                f'Disponible: {stock_location.quantity}, Solicitado: {quantity}'
                    })
                
            except InventoryStock.DoesNotExist:
                raise serializers.ValidationError({
                    'items': f'No hay stock del producto {product.name} en {location.name}'
                })

    def _process_composite_sale(self, product, batch, quantity, sale, location):
        """Procesa la venta de un producto compuesto (kit/caja)."""
        # Verificar stock del producto compuesto
        self._check_and_reserve_stock(product, batch, quantity, location)
        
        # Crear movimiento de salida del producto compuesto
        # Esto automáticamente creará movimientos de "composite_conversion" para los componentes
        InventoryMovement.objects.create(
            product=product,
            location=location,
            batch=batch,
            movement_type='out',
            quantity=quantity,
            notes=f'Venta #{sale.id} - Producto compuesto'
        )

    def _process_component_sale(self, product, batch, quantity, sale, location):
        """
        Procesa la venta de un componente individual.
        Verifica stock directo primero, luego puede usar kits automáticamente.
        """
        # 1. Consumir stock directo disponible del componente
        available_component_stock = self._get_available_stock(product, batch, location)

        if available_component_stock >= quantity:
            # Hay suficiente stock directo; simple salida
            self._create_sale_movement(product, batch, quantity, sale, location, 'Componente individual')
            return

        # Consumir stock directo parcial si lo hay
        sold_from_direct = 0
        if available_component_stock > 0:
            self._create_sale_movement(product, batch, available_component_stock, sale, location, 'Componente individual')
            sold_from_direct = available_component_stock

        remaining_quantity = quantity - sold_from_direct

        # 2. Elaborar un plan de ruptura priorizando cajas homogéneas
        breakdown_plan = self._plan_breakdown(product, remaining_quantity, location)

        # Si el usuario no confirmó, devolver plan con 409
        if not getattr(self, '_confirm_breakdown', False):
            raise BreakdownConfirmationRequired(detail={
                'breakdown_plan': breakdown_plan,
                'message': 'Se requiere confirmación para desarmar las composiciones indicadas.'
            })

        # 3. Ejecutar el plan
        obtained_from_breakdown = self._execute_breakdown_plan(breakdown_plan, sale, location)

        # 4. Registrar la salida de los componentes necesarios (puede ser <= obtenidos)
        self._create_sale_movement(
            product,
            batch,
            remaining_quantity,
            sale,
            location,
            'Componente obtenido de desarmado automático'
        )

    def _process_simple_sale(self, product, batch, quantity, sale, location):
        """Procesa la venta de un producto simple."""
        self._check_and_reserve_stock(product, batch, quantity, location)
        self._create_sale_movement(product, batch, quantity, sale, location, 'Producto simple')

    def _get_available_stock(self, product, batch, location):
        """Obtiene el stock disponible de un producto en una ubicación."""
        try:
            if product.requires_batch_control and batch:
                stock = InventoryStock.objects.get(product=product, location=location, batch=batch)
            else:
                stock = InventoryStock.objects.get(product=product, location=location, batch__isnull=True)
            return stock.quantity
        except InventoryStock.DoesNotExist:
            return 0

    def _find_kits_containing_component(self, component_product, location):
        """Encuentra kits que contengan el componente especificado y tienen stock disponible."""
        kits_info = []
        
        # Buscar todos los kits que contienen este componente
        component_relations = ProductComponent.objects.filter(component_product=component_product)
        
        for relation in component_relations:
            kit_product = relation.composite_product
            kit_stock = self._get_available_stock(kit_product, None, location)
            
            if kit_stock > 0:
                kits_info.append({
                    'kit': kit_product,
                    'quantity': relation.quantity,  # Cantidad de componentes por kit
                    'available_kits': kit_stock
                })
        
        # Ordenar por eficiencia (más componentes por kit primero)
        kits_info.sort(key=lambda x: x['quantity'], reverse=True)
        return kits_info

    def _calculate_total_available_components(self, component_product, location):
        """Calcula el total de componentes disponibles (directo + de kits)."""
        # Stock directo del componente
        direct_stock = 0
        direct_stocks = InventoryStock.objects.filter(
            product=component_product,
            location=location
        )
        direct_stock = sum(stock.quantity for stock in direct_stocks)
        
        # Stock de componentes en kits
        kit_stock = 0
        component_relations = ProductComponent.objects.filter(component_product=component_product)
        
        for relation in component_relations:
            kit_product = relation.composite_product
            kit_available = self._get_available_stock(kit_product, None, location)
            kit_stock += kit_available * relation.quantity
        
        return direct_stock + kit_stock

    def _breakdown_kits_for_components(self, component_product, batch, needed_quantity, sale, location):
        """Desarma kits automáticamente para obtener componentes."""
        kits_with_component = self._find_kits_containing_component(component_product, location)
        remaining_quantity = needed_quantity
        
        for kit_info in kits_with_component:
            if remaining_quantity <= 0:
                break
            
            kit_product = kit_info['kit']
            components_per_kit = kit_info['quantity']
            kit_stock = self._get_available_stock(kit_product, None, location)
            
            # Calcular cuántos kits necesitamos desarmar
            kits_needed = (remaining_quantity + components_per_kit - 1) // components_per_kit  # Redondeo hacia arriba
            kits_to_use = min(kits_needed, kit_stock)
            
            if kits_to_use > 0:
                # Desarmar los kits necesarios
                breakdown_movement = InventoryMovement.create_composite_breakdown(
                    composite_product=kit_product,
                    location=location,
                    quantity=kits_to_use,
                    notes=f'Desarmado automático para venta #{sale.id}'
                )
                
                components_obtained = kits_to_use * components_per_kit
                components_to_sell = min(components_obtained, remaining_quantity)
                
                # Crear movimiento de salida para los componentes del desarmado
                # Usar el mismo lote que se especificó en la venta para componentes de desarmado
                self._create_sale_movement(component_product, batch, components_to_sell, sale, location, 
                                         f'De desarmado de {kits_to_use} unidades de {kit_product.name}')
                
                remaining_quantity -= components_to_sell

    def _create_sale_movement(self, product, batch, quantity, sale, location, notes_suffix):
        """Crea un movimiento de inventario para la venta."""
        InventoryMovement.objects.create(
            product=product,
            location=location,
            batch=batch,
            movement_type='out',
            quantity=quantity,
            notes=f'Venta #{sale.id} - {notes_suffix}'
        )

    def validate_items(self, items):
        """Valida que la venta tenga al menos un item."""
        if not items:
            raise serializers.ValidationError("Se requiere al menos un item en la venta.")
        return items

    def validate(self, data):
        """Validaciones de la venta completa, incluyendo stock."""
        items = data.get('items', [])
        location = data.get('location')
        
        if not location:
            raise serializers.ValidationError("Se requiere especificar una ubicación.")
            
        # Validar stock para cada item
        validation_errors = {}
        for idx, item_data in enumerate(items):
            product = item_data.get('product')
            batch = item_data.get('batch')
            quantity = item_data.get('quantity')
            
            if not product or not quantity:
                continue
                
            try:
                # Validar según el tipo de producto
                if product.is_composite():
                    # Validar stock de producto compuesto
                    self._validate_composite_stock(product, batch, quantity, location)
                elif product.is_component():
                    # Validar stock total de componente (directo + de kits)
                    self._validate_component_stock(product, batch, quantity, location)
                else:
                    # Validar stock de producto simple
                    self._validate_simple_stock(product, batch, quantity, location)
            except serializers.ValidationError as e:
                validation_errors[f'items[{idx}]'] = e.detail
        
        if validation_errors:
            raise serializers.ValidationError(validation_errors)
        
        return data

    def _validate_composite_stock(self, product, batch, quantity, location):
        """Valida que hay suficiente stock del producto compuesto."""
        try:
            self._check_and_reserve_stock(product, batch, quantity, location)
        except serializers.ValidationError:
            raise
    
    def _validate_component_stock(self, product, batch, quantity, location):
        """Valida que hay suficiente stock del componente."""
        # Si se especifica un lote específico, validar solo ese lote
        if batch and product.requires_batch_control:
            self._check_and_reserve_stock(product, batch, quantity, location)
            return
        
        # Si no se especifica lote o no requiere control de lotes, 
        # validar stock total disponible (directo + de kits)
        total_available = self._calculate_total_available_components(product, location)
        
        if total_available < quantity:
            raise serializers.ValidationError(
                f'Stock insuficiente del componente {product.name} en {location.name}. '
                f'Disponible total: {total_available}, Solicitado: {quantity}'
            )
    
    def _validate_simple_stock(self, product, batch, quantity, location):
        """Valida que hay suficiente stock del producto simple."""
        try:
            self._check_and_reserve_stock(product, batch, quantity, location)
        except serializers.ValidationError:
            raise

    # ------------------------------------------------------------------
    # NUEVA LÓGICA DE DESARME PRIORIZADA
    # ------------------------------------------------------------------

    def _plan_breakdown(self, component_product, needed_quantity, location):
        """Devuelve un plan de ruptura (lista de acciones) para obtener la cantidad necesaria.

        La prioridad es:
            1. Cajas homogéneas (boxed_component) ordenadas por menor tamaño (menos sobrante).
            2. Kits mixtos (mixed_kit) ordenados por mayor cantidad del componente por kit.
        Cada acción es un dict:
            {
                'kit_id': <Producto a romper>,
                'kit_name': str,
                'units_to_break': int,
                'components_per_unit': int,
                'components_obtained': int
            }
        """
        actions = []
        remaining = needed_quantity

        # Paso 1: cajas homogéneas
        box_relations = ProductComponent.objects.filter(
            component_product=component_product,
            composite_product__product_type='boxed_component'
        )

        # Map kit -> components_per_unit
        box_infos = []
        for rel in box_relations:
            kit_product = rel.composite_product
            available_kits = self._get_available_stock(kit_product, None, location)
            if available_kits > 0:
                box_infos.append({
                    'kit': kit_product,
                    'components_per_unit': rel.quantity,
                    'available_kits': available_kits
                })

        # Ordenar por tamaño ascendente para minimizar excedentes
        box_infos.sort(key=lambda x: x['components_per_unit'])

        for info in box_infos:
            if remaining <= 0:
                break

            components_per_unit = info['components_per_unit']
            kits_needed = (remaining + components_per_unit - 1) // components_per_unit
            kits_to_break = min(kits_needed, info['available_kits'])

            if kits_to_break <= 0:
                continue

            components_obtained = kits_to_break * components_per_unit
            actions.append({
                'kit': info['kit'],
                'units_to_break': kits_to_break,
                'components_per_unit': components_per_unit,
                'components_obtained': components_obtained
            })

            remaining -= components_obtained

        # Paso 2: kits mixtos si aún falta
        if remaining > 0:
            kit_relations = ProductComponent.objects.filter(
                component_product=component_product,
                composite_product__product_type='mixed_kit'
            )

            kit_infos = []
            for rel in kit_relations:
                kit_product = rel.composite_product
                available_kits = self._get_available_stock(kit_product, None, location)
                if available_kits > 0:
                    kit_infos.append({
                        'kit': kit_product,
                        'components_per_unit': rel.quantity,
                        'available_kits': available_kits
                    })

            # Ordenar por eficiencia (más componentes por kit primero)
            kit_infos.sort(key=lambda x: x['components_per_unit'], reverse=True)

            for info in kit_infos:
                if remaining <= 0:
                    break

                components_per_unit = info['components_per_unit']
                kits_needed = (remaining + components_per_unit - 1) // components_per_unit
                kits_to_break = min(kits_needed, info['available_kits'])

                if kits_to_break <= 0:
                    continue

                components_obtained = kits_to_break * components_per_unit
                actions.append({
                    'kit': info['kit'],
                    'units_to_break': kits_to_break,
                    'components_per_unit': components_per_unit,
                    'components_obtained': components_obtained
                })

                remaining -= components_obtained

        # Validar que el plan cubra la necesidad
        total_obtained = sum(a['components_obtained'] for a in actions)
        if total_obtained < needed_quantity:
            raise serializers.ValidationError(
                f'No hay suficiente stock (cajas/kits) para obtener {needed_quantity} unidades de {component_product.name}. '
                f'Solo se pueden obtener {total_obtained} unidades.'
            )

        # Serializar plan a un formato amigable para la API (sin objetos Django para evitar problemas de JSON)
        serialized_actions = [
            {
                'kit_id': a['kit'].id,
                'kit_name': a['kit'].name,
                'units_to_break': a['units_to_break'],
                'components_per_unit': a['components_per_unit'],
                'components_obtained': a['components_obtained']
            }
            for a in actions
        ]

        return serialized_actions

    def _execute_breakdown_plan(self, plan, sale, location):
        """Ejecuta las acciones de ruptura y retorna la cantidad total obtenida."""
        total_obtained = 0
        for action in plan:
            kit_product = Product.objects.get(pk=action['kit_id'])
            units_to_break = action['units_to_break']

            InventoryMovement.create_composite_breakdown(
                composite_product=kit_product,
                location=location,
                quantity=units_to_break,
                notes=f'Desarmado automático por venta #{sale.id}'
            )

            total_obtained += action['components_obtained']
        return total_obtained


class ReturnItemSerializer(serializers.ModelSerializer):
    """Serializador para los items de devolución."""
    
    product_details = ProductSerializer(source='product', read_only=True)
    sale_item_details = SaleItemSerializer(source='sale_item', read_only=True)
    
    class Meta:
        model = ReturnItem
        fields = [
            'id', 'return_obj', 'sale_item', 'sale_item_details', 
            'product', 'product_details', 'quantity_returned', 
            'unit_price', 'subtotal'
        ]
        read_only_fields = ['subtotal']
        extra_kwargs = {'return_obj': {'required': False}}
    
    def update(self, instance, validated_data):
        """
        Actualiza un item de devolución y ajusta el inventario.
        """
        original_quantity = instance.quantity_returned
        
        # Actualiza la instancia con la nueva cantidad
        instance.quantity_returned = validated_data.get('quantity_returned', original_quantity)
        instance.save()

        # Ajustar inventario para la diferencia
        quantity_diff = instance.quantity_returned - original_quantity
        if quantity_diff != 0:
            InventoryMovement.objects.create(
                product=instance.product,
                location=instance.return_obj.location,
                movement_type='in' if quantity_diff > 0 else 'out',
                quantity=abs(quantity_diff),
                notes=f'Ajuste por actualización de item de devolución #{instance.id}'
            )

        return instance

    def validate(self, data):
        """Validaciones del item de devolución."""
        # Durante una actualización, algunos campos no estarán en `data`
        sale_item = data.get('sale_item') or getattr(self.instance, 'sale_item', None)
        product = data.get('product') or getattr(self.instance, 'product', None)
        quantity_returned = data.get('quantity_returned')

        if not sale_item or not product or quantity_returned is None:
            raise serializers.ValidationError("Faltan campos requeridos (sale_item, product, quantity_returned).")

        # Validar que el producto corresponde al item de venta
        if 'product' in data and product != sale_item.product:
            raise serializers.ValidationError({
                'product': 'El producto debe corresponder al item de venta original.'
            })
        
        # Validar cantidad disponible para devolver
        already_returned_qs = ReturnItem.objects.filter(sale_item=sale_item)
        if self.instance:
            already_returned_qs = already_returned_qs.exclude(pk=self.instance.pk)
            
        already_returned = already_returned_qs.aggregate(
            total=models.Sum('quantity_returned')
        )['total'] or 0
        
        available_to_return = sale_item.quantity - already_returned
        
        if quantity_returned > available_to_return:
            raise serializers.ValidationError({
                'quantity_returned': f'No se puede devolver más cantidad de la disponible. '
                                   f'Disponible para devolver: {available_to_return}'
            })
        
        return data


class ReturnSerializer(serializers.ModelSerializer):
    """Serializador para las devoluciones con soporte para items anidados."""
    
    items = ReturnItemSerializer(many=True, required=False)
    customer_details = CustomerSerializer(source='customer', read_only=True)
    location_details = LocationSerializer(source='location', read_only=True)
    original_sale_details = SaleSerializer(source='original_sale', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = Return
        fields = [
            'id', 'original_sale', 'original_sale_details', 'customer', 
            'customer_details', 'location', 'location_details', 'return_date', 
            'reason', 'reason_display', 'notes', 'total_amount', 'items'
        ]
        read_only_fields = ['return_date', 'total_amount']
    
    def create(self, validated_data):
        """
        Crea una devolución con sus items asociados.
        La lógica de inventario se maneja por señales en el modelo ReturnItem.
        """
        items_data = validated_data.pop('items', [])
        return_obj = Return.objects.create(**validated_data)
        
        for item_data in items_data:
            ReturnItem.objects.create(return_obj=return_obj, **item_data)
        
        return return_obj
    
    def update(self, instance, validated_data):
        """
        Actualiza una devolución. No se permite cambiar la venta original ni los items.
        """
        validated_data.pop('items', None) # No se gestionan items aquí
        validated_data.pop('original_sale', None) # No se puede cambiar la venta original
        return super().update(instance, validated_data)

    def validate(self, data):
        """Validaciones de la devolución."""
        
        # En creación, la venta original es obligatoria
        if not self.instance and 'original_sale' not in data:
            raise serializers.ValidationError({'original_sale': 'Este campo es requerido.'})

        # Validar que el cliente de la devolución corresponde al de la venta
        original_sale = data.get('original_sale') or getattr(self.instance, 'original_sale', None)
        if data.get('customer') and original_sale and data['customer'] != original_sale.customer:
            raise serializers.ValidationError({
                'customer': 'El cliente de la devolución no coincide con el de la venta original.'
            })
            
        return data

    def validate_items(self, items):
        """Valida que la devolución tenga al menos un item."""
        if not items:
            raise serializers.ValidationError("Se requiere al menos un item en la devolución.")
        return items


class ReturnItemSummarySerializer(serializers.ModelSerializer):
    """Serializador liviano para listados de items de devolución - OPTIMIZADO."""
    
    product_details = ProductSummarySerializer(source='product', read_only=True)
    return_id = serializers.IntegerField(source='return_obj.id', read_only=True)
    sale_id = serializers.IntegerField(source='sale_item.sale.id', read_only=True)
    
    class Meta:
        model = ReturnItem
        fields = [
            'id', 'return_id', 'sale_id', 'product_details', 
            'quantity_returned', 'unit_price', 'subtotal'
        ]
        read_only_fields = ['subtotal']


class ReturnSummarySerializer(serializers.ModelSerializer):
    """Serializador liviano para listados de devoluciones - OPTIMIZADO."""
    
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    original_sale_id = serializers.IntegerField(source='original_sale.id', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = Return
        fields = [
            'id', 'original_sale_id', 'customer_name', 'location_name', 
            'return_date', 'reason', 'reason_display', 'total_amount'
        ]


# --- Excepciones personalizadas ---


class BreakdownConfirmationRequired(APIException):
    """Se lanza cuando se requiere confirmación explícita para desarmar cajas/kits."""

    status_code = status.HTTP_409_CONFLICT
    default_code = 'breakdown_confirmation_required'
    default_detail = 'Se requiere confirmación para desarmar composiciones de inventario.' 