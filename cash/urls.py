from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import CashesViewSet, MovementsViewSet, TransfersViewSet

router = DefaultRouter()
router.register(r'cashes', CashesViewSet, basename='cashes')
router.register(r'movements', MovementsViewSet, basename='movements')
router.register(r'transfers', TransfersViewSet, basename='transfers')

urlpatterns = [
    path('', include(router.urls)),
] 