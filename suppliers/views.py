from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from django.db import models

from .models import Supplier, PurchaseOption
from .serializers import (
    SupplierSerializer, 
    SupplierDetailSerializer,
    PurchaseOptionSerializer, 
    PurchaseOptionDetailSerializer
)
from .filters import SupplierFilter, PurchaseOptionFilter


class SupplierViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar proveedores.
    
    Permite operaciones CRUD completas sobre los proveedores del sistema.
    """
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filterset_class = SupplierFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'contact_name', 'email']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']

    def get_serializer_class(self):
        """
        Retorna el serializer apropiado según la acción.
        """
        if self.action == 'retrieve':
            return SupplierDetailSerializer
        return SupplierSerializer

    @swagger_auto_schema(
        operation_summary="Listar proveedores",
        operation_description="Obtiene una lista paginada de todos los proveedores del sistema.",
        responses={
            200: openapi.Response(
                description="Lista de proveedores obtenida exitosamente",
                schema=SupplierSerializer(many=True)
            )
        }
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Crear proveedor",
        operation_description="Crea un nuevo proveedor en el sistema.",
        request_body=SupplierSerializer,
        responses={
            201: openapi.Response(
                description="Proveedor creado exitosamente",
                schema=SupplierSerializer
            ),
            400: openapi.Response(description="Datos inválidos")
        }
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Obtener proveedor",
        operation_description="Obtiene los detalles de un proveedor específico incluyendo sus opciones de compra.",
        responses={
            200: openapi.Response(
                description="Detalles del proveedor obtenidos exitosamente",
                schema=SupplierDetailSerializer
            ),
            404: openapi.Response(description="Proveedor no encontrado")
        }
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Actualizar proveedor",
        operation_description="Actualiza completamente un proveedor existente.",
        request_body=SupplierSerializer,
        responses={
            200: openapi.Response(
                description="Proveedor actualizado exitosamente",
                schema=SupplierSerializer
            ),
            404: openapi.Response(description="Proveedor no encontrado"),
            400: openapi.Response(description="Datos inválidos")
        }
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Actualizar parcialmente proveedor",
        operation_description="Actualiza parcialmente un proveedor existente.",
        request_body=SupplierSerializer,
        responses={
            200: openapi.Response(
                description="Proveedor actualizado exitosamente",
                schema=SupplierSerializer
            ),
            404: openapi.Response(description="Proveedor no encontrado"),
            400: openapi.Response(description="Datos inválidos")
        }
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Eliminar proveedor",
        operation_description="Elimina un proveedor del sistema.",
        responses={
            204: openapi.Response(description="Proveedor eliminado exitosamente"),
            404: openapi.Response(description="Proveedor no encontrado")
        }
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Opciones de compra del proveedor",
        operation_description="Obtiene todas las opciones de compra asociadas a un proveedor específico.",
        responses={
            200: openapi.Response(
                description="Opciones de compra obtenidas exitosamente",
                schema=PurchaseOptionSerializer(many=True)
            ),
            404: openapi.Response(description="Proveedor no encontrado")
        }
    )
    @action(detail=True, methods=['get'])
    def purchase_options(self, request, pk=None):
        """
        Obtiene todas las opciones de compra para un proveedor específico.
        """
        supplier = self.get_object()
        options = supplier.purchase_options.all()
        serializer = PurchaseOptionSerializer(options, many=True)
        return Response(serializer.data)


class PurchaseOptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar opciones de compra.
    
    Permite gestionar las opciones de compra que relacionan productos con proveedores,
    incluyendo precios y marcas específicas.
    """
    queryset = PurchaseOption.objects.select_related('product', 'supplier', 'product__category').all()
    serializer_class = PurchaseOptionSerializer
    filterset_class = PurchaseOptionFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['product__name', 'supplier__name', 'brand']
    ordering_fields = ['purchase_price', 'valid_from', 'valid_to', 'created_at']
    ordering = ['-valid_from', 'product__name']

    def get_serializer_class(self):
        """
        Retorna el serializer apropiado según la acción.
        """
        if self.action == 'retrieve':
            return PurchaseOptionDetailSerializer
        return PurchaseOptionSerializer

    @swagger_auto_schema(
        operation_summary="Listar opciones de compra",
        operation_description="Obtiene una lista paginada de todas las opciones de compra del sistema.",
        responses={
            200: openapi.Response(
                description="Lista de opciones de compra obtenida exitosamente",
                schema=PurchaseOptionSerializer(many=True)
            )
        }
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Crear opción de compra",
        operation_description="Crea una nueva opción de compra relacionando un producto con un proveedor.",
        request_body=PurchaseOptionSerializer,
        responses={
            201: openapi.Response(
                description="Opción de compra creada exitosamente",
                schema=PurchaseOptionSerializer
            ),
            400: openapi.Response(description="Datos inválidos")
        }
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Obtener opción de compra",
        operation_description="Obtiene los detalles de una opción de compra específica.",
        responses={
            200: openapi.Response(
                description="Detalles de la opción de compra obtenidos exitosamente",
                schema=PurchaseOptionDetailSerializer
            ),
            404: openapi.Response(description="Opción de compra no encontrada")
        }
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Actualizar opción de compra",
        operation_description="Actualiza completamente una opción de compra existente.",
        request_body=PurchaseOptionSerializer,
        responses={
            200: openapi.Response(
                description="Opción de compra actualizada exitosamente",
                schema=PurchaseOptionSerializer
            ),
            404: openapi.Response(description="Opción de compra no encontrada"),
            400: openapi.Response(description="Datos inválidos")
        }
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Actualizar parcialmente opción de compra",
        operation_description="Actualiza parcialmente una opción de compra existente.",
        request_body=PurchaseOptionSerializer,
        responses={
            200: openapi.Response(
                description="Opción de compra actualizada exitosamente",
                schema=PurchaseOptionSerializer
            ),
            404: openapi.Response(description="Opción de compra no encontrada"),
            400: openapi.Response(description="Datos inválidos")
        }
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Eliminar opción de compra",
        operation_description="Elimina una opción de compra del sistema.",
        responses={
            204: openapi.Response(description="Opción de compra eliminada exitosamente"),
            404: openapi.Response(description="Opción de compra no encontrada")
        }
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Opciones válidas actualmente",
        operation_description="Obtiene todas las opciones de compra que están válidas en la fecha actual.",
        responses={
            200: openapi.Response(
                description="Opciones válidas obtenidas exitosamente",
                schema=PurchaseOptionSerializer(many=True)
            )
        }
    )
    @action(detail=False, methods=['get'])
    def valid_options(self, request):
        """
        Obtiene opciones de compra que están válidas actualmente.
        """
        today = timezone.localdate()
        
        valid_options = self.get_queryset().filter(
            valid_from__lte=today
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=today)
        )
        
        page = self.paginate_queryset(valid_options)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(valid_options, many=True)
        return Response(serializer.data)
