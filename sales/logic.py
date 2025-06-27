from django.db import transaction
from inventory.models import InventoryMovement, InventoryStock
from catalogs.models import Product, ProductComponent

def _update_inventory_for_return(return_item, factor):
    """
    Procesa o revierte el movimiento de inventario para un item devuelto.
    - factor = 1 para procesar la devolución (incrementar stock).
    - factor = -1 para revertir la devolución (disminuir stock).
    """
    product = return_item.product
    location = return_item.return_obj.location
    quantity = return_item.quantity_returned * factor
    batch = return_item.sale_item.batch
    
    movement_type = 'in' if factor == 1 else 'out'
    notes_action = "Devolución" if factor == 1 else "Reversión de devolución"

    # Caso 1: El producto devuelto es una 'caja' (composite)
    if product.product_type == 'composite':
        # 1. Crear movimiento para el producto compuesto (caja)
        # Los productos compuestos generalmente no requieren control de lotes
        composite_batch = batch if product.requires_batch_control else None
        InventoryMovement.objects.create(
            product=product,
            location=location,
            batch=composite_batch,
            movement_type=movement_type,
            quantity=abs(quantity),
            notes=f'{notes_action} de producto compuesto (Devolución #{return_item.return_obj.id})'
        )
        
        # 2. Aumentar el stock de sus componentes
        for component_link in product.composite_components.all():
            component = component_link.component_product
            component_quantity = component_link.quantity * quantity
            
            # Para productos compuestos, devolvemos los componentes al lote más próximo a vencer
            # usando la misma lógica FIFO que se usó en la venta
            component_batch = None
            if component.requires_batch_control:
                # Buscar el lote más próximo a vencer con stock (para devolver)
                from inventory.models import InventoryStock
                stock_entry = InventoryStock.objects.filter(
                    product=component,
                    location=location,
                    batch__isnull=False
                ).order_by('batch__expiry_date').first()
                
                if stock_entry:
                    component_batch = stock_entry.batch
            
            InventoryMovement.objects.create(
                product=component,
                location=location,
                batch=component_batch,
                movement_type=movement_type,
                quantity=abs(component_quantity),
                notes=f'{notes_action} de componente via caja {product.name} (Devolución #{return_item.return_obj.id})'
            )

    # Caso 2: El producto devuelto es un 'componente'
    elif product.product_type == 'component':
        # Simplemente se actualiza el stock del componente devuelto.
        # La lógica de re-ensamblaje no debe activarse aquí, ya que el objetivo
        # es solo restaurar el item al inventario.
        component_batch = batch if product.requires_batch_control else None
        InventoryMovement.objects.create(
            product=product,
            location=location,
            movement_type=movement_type,
            quantity=abs(quantity),
            batch=component_batch,
            notes=f'{notes_action} por item #{return_item.id}'
        )

    # Caso 3: Es un producto 'simple'
    else:
        simple_batch = batch if product.requires_batch_control else None
        InventoryMovement.objects.create(
            product=product,
            location=location,
            movement_type=movement_type,
            quantity=abs(quantity),
            batch=simple_batch,
            notes=f'{notes_action} por item #{return_item.id}'
        )

@transaction.atomic
def process_return_item(return_item):
    """Procesa el movimiento de inventario para un item devuelto."""
    _update_inventory_for_return(return_item, factor=1)

@transaction.atomic
def reverse_return_item(return_item):
    """Revierte el movimiento de inventario para un item de devolución eliminado."""
    _update_inventory_for_return(return_item, factor=-1)


def _check_and_restock_composites(component, location):
    """
    Verifica si la devolución de un componente permite re-completar el stock de un producto compuesto (caja).
    """
    # Encontrar todas las 'cajas' que contienen este 'componente'
    composite_links = ProductComponent.objects.filter(component_product=component)
    
    for link in composite_links:
        composite = link.composite_product
        
        can_restock = True
        
        # Verificar si hay stock suficiente de TODOS los componentes para esta caja
        for required_component_link in composite.composite_components.all():
            req_comp = required_component_link.component_product
            req_qty = required_component_link.quantity
            
            stock = InventoryStock.objects.filter(product=req_comp, location=location).first()
            
            # Ajuste clave: si estamos comprobando el mismo componente que se devolvió,
            # su stock ya se incrementó. Debemos comprobar si, DESPUÉS de usarlo para
            # re-ensamblar, sigue habiendo suficiente.
            current_stock_quantity = stock.quantity if stock else 0
            
            if not stock or current_stock_quantity < req_qty:
                can_restock = False
                break
        
        # Si hay suficientes componentes, se "re-ensambla" la caja
        if can_restock:
            # 1. Incrementar el stock de la caja
            InventoryMovement.objects.create(
                product=composite,
                location=location,
                # Las cajas/kits pueden tener su propio lote, pero en el re-ensamblaje
                # desde componentes sueltos, no se asigna un lote específico para la caja.
                batch=None, 
                movement_type='composite_assembly',
                quantity=1,
                notes=f'Re-ensamblaje de caja por devolución de {component.name}'
            )
            
            # 2. Descontar el stock de los componentes utilizados
            for required_component_link in composite.composite_components.all():
                req_comp = required_component_link.component_product
                req_qty = required_component_link.quantity

                # Si un componente requiere lote, debemos encontrar un lote con stock suficiente.
                # Aquí asumimos una estrategia FIFO (First-In, First-Out) para simplicidad,
                # usando el lote más antiguo con stock disponible.
                component_batch = None
                if req_comp.requires_batch_control:
                    stock_entry = InventoryStock.objects.filter(
                        product=req_comp,
                        location=location,
                        quantity__gte=req_qty,
                        batch__isnull=False
                    ).order_by('batch__expiry_date').first()

                    if not stock_entry:
                        # Este caso no debería ocurrir si `can_restock` es verdadero,
                        # pero es una salvaguarda.
                        continue
                    
                    component_batch = stock_entry.batch

                # Registrar el movimiento de salida del componente
                InventoryMovement.objects.create(
                    product=req_comp,
                    location=location,
                    batch=component_batch,
                    movement_type='out',
                    quantity=req_qty,
                    notes=f'Uso de componente para re-ensamblaje de {composite.name}'
                ) 