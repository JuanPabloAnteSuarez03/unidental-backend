from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import CashViewSet, CashMovementViewSet, CashTransferViewSet

router = DefaultRouter()
router.register(r'cashes', CashViewSet, basename='cash')
router.register(r'movements', CashMovementViewSet, basename='cashmovement')
router.register(r'transfers', CashTransferViewSet, basename='cashtransfer')

urlpatterns = [
    path('', include(router.urls)),
] 