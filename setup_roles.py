#!/usr/bin/env python
"""
Script para configurar el sistema de roles Admin y User.
Ejecutar después de las migraciones.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unidental.settings')
django.setup()

from django.contrib.auth.models import User, Group
from django.core.management import call_command


def setup_roles():
    """Configurar los roles del sistema."""
    print("🔐 Configurando sistema de roles...")
    
    # 1. Crear grupos
    print("\n1. Creando grupos...")
    call_command('create_roles')
    
    # 2. Crear usuario administrador si no existe
    print("\n2. Verificando usuario administrador...")
    admin_user, created = User.objects.get_or_create(
        username='admin_unidental',
        defaults={
            'email': 'admin@unidental.com',
            'first_name': 'Admin',
            'last_name': 'Unidental',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    
    if created:
        admin_user.set_password('admin123')  # Cambiar en producción
        admin_user.save()
        print("  ✅ Usuario administrador creado")
    else:
        print("  ℹ️  Usuario administrador ya existe")
    
    # 3. Asignar grupo Admin al usuario administrador
    try:
        admin_group = Group.objects.get(name='Admin')
        admin_user.groups.add(admin_group)
        print("  ✅ Usuario administrador asignado al grupo Admin")
    except Group.DoesNotExist:
        print("  ⚠️  Grupo Admin no encontrado")
    
    print("\n🎉 Configuración completada!")
    print("\n📋 Resumen:")
    print("  • Grupos creados: Admin, User")
    print("  • Usuario administrador: admin_unidental / admin123")
    print("  • Endpoints protegidos: Caja y Créditos (solo Admin)")
    print("  • Registro de usuarios: Solo crea usuarios con rol User")


if __name__ == '__main__':
    setup_roles() 