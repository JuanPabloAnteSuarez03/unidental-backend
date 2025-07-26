from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Crea los grupos de roles Admin y User con sus permisos correspondientes'

    def handle(self, *args, **options):
        self.stdout.write("🔐 Creando grupos de roles...")

        # Crear grupo Admin
        admin_group, created = Group.objects.get_or_create(name='Admin')
        if created:
            self.stdout.write("  ✅ Grupo 'Admin' creado")
        else:
            self.stdout.write("  ℹ️  Grupo 'Admin' ya existe")

        # Crear grupo User
        user_group, created = Group.objects.get_or_create(name='User')
        if created:
            self.stdout.write("  ✅ Grupo 'User' creado")
        else:
            self.stdout.write("  ℹ️  Grupo 'User' ya existe")

        # Asignar todos los permisos al grupo Admin
        all_permissions = Permission.objects.all()
        admin_group.permissions.set(all_permissions)
        self.stdout.write(f"  ✅ {all_permissions.count()} permisos asignados al grupo Admin")

        # Para el grupo User, asignar solo permisos básicos (sin caja ni créditos)
        # Obtener content types de las apps que queremos permitir
        allowed_apps = ['catalogs', 'sales', 'inventory', 'purchases', 'suppliers', 'deliveries']
        
        user_permissions = []
        for app_name in allowed_apps:
            try:
                # Obtener permisos de las apps permitidas
                app_permissions = Permission.objects.filter(
                    content_type__app_label__in=allowed_apps
                )
                user_permissions.extend(app_permissions)
            except Exception as e:
                self.stdout.write(f"  ⚠️  Error con app {app_name}: {e}")

        # También agregar permisos básicos de autenticación
        auth_permissions = Permission.objects.filter(
            content_type__app_label='auth'
        )
        user_permissions.extend(auth_permissions)

        # Asignar permisos al grupo User
        user_group.permissions.set(user_permissions)
        self.stdout.write(f"  ✅ {len(user_permissions)} permisos asignados al grupo User")

        self.stdout.write(self.style.SUCCESS("🎉 Grupos de roles creados exitosamente!"))
        self.stdout.write("\n📋 Resumen:")
        self.stdout.write("  • Admin: Acceso completo a todas las funcionalidades")
        self.stdout.write("  • User: Acceso limitado (sin caja ni créditos)") 