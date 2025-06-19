# unidental/test_settings.py
# Este archivo contiene la configuración de Django exclusiva para el entorno de tests.
# Es activado por la configuración DJANGO_SETTINGS_MODULE en pytest.ini.

# Importar todas las configuraciones del archivo principal.
from .settings import *

# ==============================================================================
# CONFIGURACIÓN DE TESTS
# ==============================================================================

# BASE DE DATOS
# ------------------------------------------------------------------------------
# Sobrescribir la configuración de la base de datos para usar una base de datos
# SQLite en memoria. Esto es rápido, aislado y no requiere un servidor de BD.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# HASHING DE CONTRASEÑAS
# ------------------------------------------------------------------------------
# Usar un hasher de contraseñas más rápido (inseguro para producción) para
# acelerar la creación de usuarios en los tests.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# LOGGING
# ------------------------------------------------------------------------------
# Puedes desactivar el logging para limpiar la salida de los tests si lo deseas.
# import logging
# logging.disable(logging.CRITICAL) 