#!/bin/bash
set -e

echo "🚀 Iniciando Taller Nicolas - MODO PRODUCCIÓN"

# 1. Esperar a que la base de datos esté lista
echo "⏳ Esperando a que la base de datos esté lista..."
while ! pg_isready -h db -p 5432 -U "${DB_USER}" -d "${DB_NAME}"; do
    echo "PostgreSQL no disponible - esperando..."
    sleep 2
done
echo "✅ Base de datos lista!"

# 2. Aplicar migraciones
echo "📦 Aplicando migraciones de base de datos..."
python manage.py migrate --noinput

# 3. Recopilar archivos estáticos
echo "📁 Recopilando archivos estáticos..."
python manage.py collectstatic --noinput --clear

# 4. Configuración inicial (Sucursal y Superusuario)
echo "👤 Configurando datos iniciales de sistema..."
python manage.py shell << EOF
import os
import datetime
from django.contrib.auth import get_user_model
from core.models import Sucursal, DominioSucursal

User = get_user_model()

# --- Asegurar Sucursal Matriz ---
if not Sucursal.objects.exists():
    print("Creando sucursal principal (Matriz)...")
    matriz = Sucursal.objects.create(
        codigo='MATRIZ',
        nombre='Full Motos Nicolas - Matriz',
        nombre_corto='Matriz',
        direccion='Cayambe, Ecuador',
        ciudad='Cayambe',
        provincia='Pichincha',
        es_principal=True,
        activa=True,
        fecha_apertura=datetime.date.today()
    )
    print(f"✅ Sucursal creada: {matriz.nombre}")
else:
    matriz = Sucursal.objects.filter(es_principal=True).first()
    print(f"ℹ️ Sucursal Matriz ya existe: {matriz.nombre if matriz else 'No marcada como principal'}")

# --- Asegurar Dominio ---
primary_domain = os.environ.get('PRIMARY_DOMAIN', 'full-motos-nicolas.valktek.com')
if matriz:
    obj, created = DominioSucursal.objects.get_or_create(
        domain=primary_domain,
        defaults={'tenant': matriz, 'is_primary': True}
    )
    if created:
        print(f"✅ Dominio principal configurado: {primary_domain}")

# --- Asegurar Superusuario ---
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if not all([username, email, password]):
    print("⚠️ ADVERTENCIA: Variables de superusuario incompletas. Saltando creación.")
else:
    if not User.objects.filter(usuario=username).exists():
        print(f"Creando superusuario: {username}...")
        User.objects.create_superuser(
            usuario=username,
            email=email,
            password=password,
            nombre='Administrador',
            apellido='Producción',
            sucursal=matriz
        )
        print("✅ Superusuario creado exitosamente.")
    else:
        print(f"ℹ️ El superusuario '{username}' ya existe.")

EOF

# 5. Cargar datos iniciales (fixtures)
if [ -f "/app/ventas/fixtures/initial_data.json" ]; then
    echo "📥 Cargando datos iniciales de aplicación..."
    python manage.py loaddata /app/ventas/fixtures/initial_data.json || echo "⚠️ Datos ya cargados o error menor en loaddata"
fi

echo "🔒 Iniciando servidor Daphne (ASGI) en puerto 8000..."
exec daphne -b 0.0.0.0 -p 8000 vpmotos.asgi:application