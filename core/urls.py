from django.urls import path
from .views import health_check_view, UserCreateView, UserMeView, AdminUserCreateView
 
urlpatterns = [
    path('health-check/', health_check_view, name='health-check'),
    path('users/register/', UserCreateView.as_view(), name='user-register'),
    path('users/me/', UserMeView.as_view(), name='user-me'),
    path('users/admin-create/', AdminUserCreateView.as_view(), name='admin-user-create'),
] 