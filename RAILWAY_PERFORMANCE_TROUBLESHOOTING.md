# 🚨 Guía de Solución de Problemas de Rendimiento en Railway

## 📋 Diagnóstico Inicial

Tu backend de Django está respondiendo lentamente en Railway. Aquí tienes una guía paso a paso para diagnosticar y resolver el problema:

### 1. 🏥 Ejecutar Chequeo de Salud

Primero, ejecuta el comando de diagnóstico que acabamos de crear:

```bash
# En tu entorno local conectado a la BD de producción
python manage.py health_check --full

# O solo verificar la BD
python manage.py health_check --db-only
```

### 2. 🔍 Verificar Configuración de Railway

#### Variables de Entorno Críticas:
Asegúrate de tener estas variables configuradas en Railway:

```env
DEBUG=False
CONN_MAX_AGE=600
DATABASE_CONNECTION_POOL_SIZE=3
DATABASE_MAX_CONNECTIONS=6
PYTHONUNBUFFERED=1
```

#### Comando de Inicio Optimizado:
En Railway, configura este comando de inicio:

```bash
gunicorn unidental.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --worker-class gthread --worker-connections 1000 --max-requests 1000 --max-requests-jitter 100 --timeout 120 --keep-alive 5 --preload
```

## 🚀 Posibles Causas y Soluciones

### 1. **Pool de Conexiones de Base de Datos**

**Problema:** Railway puede estar cerrando conexiones de BD demasiado rápido.

**Solución:**
```python
# En settings.py (ya configurado)
DATABASES['default']['CONN_MAX_AGE'] = 600  # 10 minutos
```

### 2. **Logging Excesivo**

**Problema:** DEBUG=True o logging excesivo puede causar lentitud.

**Verificar:**
- Confirma que `DEBUG=False` en producción
- Revisa los logs de Railway por mensajes excesivos

### 3. **Consultas N+1**

**Problema:** El código tiene buenas optimizaciones con `select_related`/`prefetch_related`, pero verifica estos endpoints:

```python
# Endpoints que podrían estar causando problemas:
- /api/sales/statistics/
- /api/credits/debt_summary/
- /api/deliveries/ (con filtros complejos)
- /api/inventory/summary/
```

### 4. **Memoria Insuficiente**

**Problema:** Railway Free tier tiene limitaciones de memoria.

**Verificar:**
- ¿Estás en el plan gratuito de Railway?
- ¿Has actualizado recientemente el plan?

### 5. **Base de Datos Sobrecargada**

**Problema:** La BD de PostgreSQL puede estar bajo carga.

**Acciones:**
1. Verifica el plan de tu base de datos
2. Considera índices adicionales
3. Revisa consultas lentas

## 🛠️ Pasos de Solución Inmediata

### Paso 1: Redeploy con Optimizaciones

1. **Actualizar Railway con el nuevo `railway.json`:**
   ```bash
   git add railway.json
   git commit -m "Add Railway performance optimizations"
   git push origin main
   ```

### Paso 2: Verificar Variables de Entorno

En el dashboard de Railway, agrega/verifica estas variables:

```
DEBUG=False
CONN_MAX_AGE=600
DATABASE_CONNECTION_POOL_SIZE=3
DATABASE_MAX_CONNECTIONS=6
PYTHONUNBUFFERED=1
```

### Paso 3: Monitorear Logs

Ejecuta en Railway CLI:
```bash
railway logs --follow
```

Busca:
- Errores de conexión a BD
- Timeouts
- Mensajes de memoria
- Consultas SQL lentas

### Paso 4: Ejecutar Health Check en Producción

Si tienes acceso a la consola de Railway:
```bash
railway run python manage.py health_check --full
```

## 📊 Métricas a Monitorear

### Tiempos de Respuesta Esperados:
- **Consultas básicas:** < 100ms
- **Consultas complejas:** < 500ms
- **Conexión a BD:** < 50ms
- **APIs simples:** < 200ms
- **APIs complejas:** < 1000ms

### Señales de Alerta:
- ❌ Consultas > 2000ms
- ❌ Conexión a BD > 200ms
- ❌ CPU > 80% constantemente
- ❌ Memoria > 90%

## 🔧 Optimizaciones Adicionales

### 1. Limitar Resultados de API

Agrega estos parámetros a endpoints problemáticos:

```python
# En views.py
pagination_class = LimitOffsetPagination
page_size = 20  # Reducir de 25 a 20
```

### 2. Caché Estratégico

```python
# Cachear consultas costosas
from django.core.cache import cache

def expensive_query():
    cache_key = 'expensive_query_result'
    result = cache.get(cache_key)
    if result is None:
        result = perform_expensive_query()
        cache.set(cache_key, result, 300)  # 5 minutos
    return result
```

### 3. Índices de Base de Datos

Considera agregar índices para consultas frecuentes:

```python
# En models.py
class Meta:
    indexes = [
        models.Index(fields=['created_at', 'status']),
        models.Index(fields=['product', 'location']),
    ]
```

## 🚨 Escalación de Problemas

### Si el problema persiste:

1. **Verificar Plan de Railway:**
   - Free tier: 512MB RAM, vCPU compartido
   - Pro tier: 8GB RAM, vCPU dedicado

2. **Migrar a Railway Pro:**
   - Más recursos garantizados
   - Mejor rendimiento de BD

3. **Alternativas:**
   - Heroku (con Redis para caché)
   - DigitalOcean App Platform
   - AWS Elastic Beanstalk

## 📞 Comandos de Diagnóstico Rápido

```bash
# 1. Verificar estado del sistema
python manage.py health_check

# 2. Ver logs en tiempo real
railway logs --follow

# 3. Verificar configuración
railway variables

# 4. Reiniciar servicio
railway redeploy

# 5. Verificar BD directamente
python manage.py dbshell
```

## 🎯 Plan de Acción Prioritario

### Inmediato (Hoy):
1. ✅ Verificar variables de entorno
2. ✅ Redeploy con optimizaciones
3. ✅ Monitorear logs

### Corto Plazo (Esta Semana):
1. 🔄 Ejecutar health_check regularmente
2. 🔄 Monitorear métricas de rendimiento
3. 🔄 Considerar upgrade de plan si es necesario

### Medio Plazo (Próximas 2 Semanas):
1. 📊 Implementar APM (Application Performance Monitoring)
2. 🗄️ Optimizar consultas más lentas
3. 💾 Implementar caché estratégico

---

**💡 Tip:** Si el problema comenzó recientemente, revisa los últimos commits y deployments para identificar qué cambió. 