from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal


class Cliente(models.Model):
    """Clientes del negocio"""
    TIPO_IDENTIFICACION_CHOICES = [
        ('CEDULA', 'Cédula'),
        ('RUC', 'RUC'),
        ('PASAPORTE', 'Pasaporte'),
    ]

    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('O', 'Otro'),
    ]

    # ── Datos básicos ──────────────────────────────────────────────
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    identificacion = models.CharField(max_length=20, unique=True)
    tipo_identificacion = models.CharField(max_length=20, choices=TIPO_IDENTIFICACION_CHOICES)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, blank=True, null=True)

    # ── Contacto ───────────────────────────────────────────────────
    telefono = models.CharField(max_length=20, blank=True, null=True)
    celular = models.CharField(max_length=20, blank=True, null=True)
    whatsapp = models.CharField(max_length=20, blank=True, null=True,
                                help_text="Número WhatsApp (con código de país, ej: 593999999999)")
    email = models.EmailField(max_length=100, blank=True, null=True)

    # ── Dirección principal ────────────────────────────────────────
    direccion = models.CharField(max_length=200, blank=True, null=True)
    ciudad = models.CharField(max_length=100, blank=True, null=True)
    provincia = models.CharField(max_length=100, blank=True, null=True)
    codigo_postal = models.CharField(max_length=10, blank=True, null=True)
    referencia_direccion = models.CharField(max_length=255, blank=True, null=True,
                                            help_text="Referencia para encontrar la dirección")

    # ── Dirección de envío alternativa ────────────────────────────
    direccion_envio = models.CharField(max_length=200, blank=True, null=True)
    ciudad_envio = models.CharField(max_length=100, blank=True, null=True)
    provincia_envio = models.CharField(max_length=100, blank=True, null=True)
    referencia_envio = models.CharField(max_length=255, blank=True, null=True)

    # ── Estado y control ──────────────────────────────────────────
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    observaciones = models.TextField(blank=True, null=True)

    # ── Sistema de puntos ─────────────────────────────────────────
    puntos_disponibles = models.PositiveIntegerField(default=0)
    puntos_acumulados = models.PositiveIntegerField(default=0)
    puntos_canjeados = models.PositiveIntegerField(default=0)

    # ── Datos comerciales ─────────────────────────────────────────
    profesion = models.CharField(max_length=100, blank=True, null=True)
    referido_por = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True,
                                     related_name='referidos')
    descuento_preferencial = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # ── Ecommerce ─────────────────────────────────────────────────
    acepta_marketing = models.BooleanField(default=False,
                                           help_text="Acepta recibir comunicaciones de marketing")
    canal_preferido = models.CharField(max_length=20, blank=True, null=True,
                                       choices=[('EMAIL', 'Email'), ('WHATSAPP', 'WhatsApp'), ('SMS', 'SMS')],
                                       help_text="Canal preferido de comunicación")
    fuente_registro = models.CharField(max_length=50, blank=True, null=True,
                                       choices=[
                                           ('TIENDA', 'Tienda física'),
                                           ('WEB', 'Tienda web'),
                                           ('REFERIDO', 'Referido'),
                                           ('REDES', 'Redes sociales'),
                                           ('OTRO', 'Otro'),
                                       ],
                                       help_text="Cómo llegó el cliente")

    class Meta:
        verbose_name = _('Cliente')
        verbose_name_plural = _('Clientes')
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.identificacion})"

    def get_nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()

    def get_direccion_envio_completa(self):
        """Retorna dirección de envío, o la principal si no tiene alternativa"""
        if self.direccion_envio:
            parts = [self.direccion_envio]
            if self.ciudad_envio:
                parts.append(self.ciudad_envio)
            if self.provincia_envio:
                parts.append(self.provincia_envio)
            return ', '.join(parts)
        return self.get_direccion_completa()

    def get_direccion_completa(self):
        parts = []
        if self.direccion:
            parts.append(self.direccion)
        if self.ciudad:
            parts.append(self.ciudad)
        if self.provincia:
            parts.append(self.provincia)
        return ', '.join(parts) if parts else ''

    def get_whatsapp_numero(self):
        """Retorna el número de WhatsApp o celular para enviar mensajes"""
        return self.whatsapp or self.celular or self.telefono or ''

    def get_total_compras(self):
        """Total gastado en ventas físicas + pedidos online completados"""
        from django.db.models import Sum
        total_pos = self.venta_set.filter(estado='COMPLETADA').aggregate(
            total=Sum('total'))['total'] or Decimal('0.00')
        total_online = self.pedidosonline.filter(estado='ENTREGADO').aggregate(
            total=Sum('total'))['total'] or Decimal('0.00')
        return total_pos + total_online

    def get_num_pedidos_online(self):
        return self.pedidosonline.exclude(estado='CANCELADO').count()

    def agregar_puntos(self, puntos, concepto="Compra", venta=None):
        if puntos > 0:
            self.puntos_disponibles += puntos
            self.puntos_acumulados += puntos
            self.save()
            MovimientoPuntos.objects.create(
                cliente=self, tipo='GANADO', puntos=puntos,
                concepto=concepto, venta=venta
            )

    def canjear_puntos(self, puntos, concepto="Canje de puntos"):
        if puntos <= self.puntos_disponibles:
            self.puntos_disponibles -= puntos
            self.puntos_canjeados += puntos
            self.save()
            MovimientoPuntos.objects.create(
                cliente=self, tipo='CANJEADO', puntos=puntos, concepto=concepto
            )
            return True
        return False

    def calcular_descuento_puntos(self, total_compra):
        descuento_max = self.puntos_disponibles * Decimal('0.01')
        descuento_limite = total_compra * Decimal('0.50')
        return min(descuento_max, descuento_limite)

    @classmethod
    def get_consumidor_final(cls):
        consumidor, _ = cls.objects.get_or_create(
            identificacion='9999999999',
            defaults={
                'nombres': 'Consumidor',
                'apellidos': 'Final',
                'tipo_identificacion': 'CEDULA',
                'direccion': '-',
                'activo': True,
                'fuente_registro': 'TIENDA',
            }
        )
        return consumidor


# ══════════════════════════════════════════════════════════════════════
#  PEDIDOS ONLINE
# ══════════════════════════════════════════════════════════════════════

class PedidoOnline(models.Model):
    """Pedidos realizados desde la tienda virtual"""

    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de confirmación'),
        ('CONFIRMADO', 'Confirmado'),
        ('PREPARANDO', 'Preparando'),
        ('DESPACHADO', 'Despachado'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]

    TIPO_ENTREGA_CHOICES = [
        ('RETIRO', 'Retiro en tienda'),
        ('SERVIENTREGA', 'Envío por Servientrega'),
    ]

    METODO_PAGO_CHOICES = [
        ('PAYPHONE', 'Payphone (tarjeta)'),
        ('TRANSFERENCIA', 'Transferencia bancaria'),
        ('CONTRA_ENTREGA', 'Pago contra entrega'),
    ]

    ESTADO_PAGO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO', 'Pagado'),
        ('FALLIDO', 'Fallido'),
        ('REEMBOLSADO', 'Reembolsado'),
    ]

    # ── Número de orden ───────────────────────────────────────────
    numero_orden = models.CharField(max_length=20, unique=True, editable=False)

    # ── Cliente (puede ser anónimo con sólo sus datos) ─────────────
    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pedidosonline',
        help_text="Cliente registrado (opcional)"
    )

    # ── Datos del comprador (siempre obligatorios) ─────────────────
    nombres_comprador = models.CharField(max_length=100)
    apellidos_comprador = models.CharField(max_length=100)
    cedula_comprador = models.CharField(max_length=20)
    telefono_comprador = models.CharField(max_length=20)
    email_comprador = models.EmailField(blank=True, null=True)

    # ── Entrega ───────────────────────────────────────────────────
    tipo_entrega = models.CharField(max_length=20, choices=TIPO_ENTREGA_CHOICES, default='RETIRO')
    direccion_envio = models.CharField(max_length=255, blank=True, null=True)
    ciudad_envio = models.CharField(max_length=100, blank=True, null=True)
    provincia_envio = models.CharField(max_length=100, blank=True, null=True)
    referencia_envio = models.CharField(max_length=255, blank=True, null=True)
    numero_guia = models.CharField(max_length=50, blank=True, null=True)

    # ── Pago ──────────────────────────────────────────────────────
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    estado_pago = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default='PENDIENTE')

    # Datos de Payphone
    payphone_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payphone_reference = models.CharField(max_length=100, blank=True, null=True)

    # ── Datos de transferencia bancaria ───────────────────────────
    # Campo legado (ImageField) — se mantiene para no romper migraciones existentes
    comprobante_transferencia = models.ImageField(
        upload_to='comprobantes/', blank=True, null=True,
        help_text="[Legado] Imagen subida por formulario"
    )
    banco_origen = models.CharField(max_length=100, blank=True, null=True,
                                    help_text="Banco desde donde se realizó la transferencia")
    numero_comprobante = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Número de comprobante',
        help_text="Número o código de referencia de la transferencia bancaria"
    )
    comprobante_base64 = models.TextField(
        blank=True,
        default='',
        verbose_name='Comprobante base64',
        help_text="Imagen del comprobante codificada en base64 (sin el prefijo data:...)"
    )
    comprobante_content_type = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name='Tipo de imagen del comprobante',
        help_text="Content-type de la imagen base64 (ej: image/jpeg)"
    )

    # ── Totales ───────────────────────────────────────────────────
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    costo_envio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # ── Estado del pedido ─────────────────────────────────────────
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')

    # ── Fechas ────────────────────────────────────────────────────
    fecha_pedido = models.DateTimeField(auto_now_add=True)
    fecha_confirmacion = models.DateTimeField(blank=True, null=True)
    fecha_despacho = models.DateTimeField(blank=True, null=True)
    fecha_entrega = models.DateTimeField(blank=True, null=True)

    # ── Notificación WhatsApp ─────────────────────────────────────
    whatsapp_enviado = models.BooleanField(default=False)
    whatsapp_enviado_at = models.DateTimeField(blank=True, null=True)

    # ── Vínculo con venta POS (cuando se procesa) ─────────────────
    venta = models.OneToOneField(
        'ventas.Venta', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pedido_online'
    )

    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _('Pedido Online')
        verbose_name_plural = _('Pedidos Online')
        ordering = ['-fecha_pedido']

    def __str__(self):
        return f"Pedido #{self.numero_orden} — {self.nombres_comprador} {self.apellidos_comprador}"

    def save(self, *args, **kwargs):
        if not self.numero_orden:
            self.numero_orden = self._generar_numero_orden()
        # Buscar o crear cliente por cédula automáticamente
        if not self.cliente and self.cedula_comprador:
            try:
                self.cliente = Cliente.objects.get(identificacion=self.cedula_comprador)
            except Cliente.DoesNotExist:
                self.cliente = Cliente.objects.create(
                    identificacion=self.cedula_comprador,
                    nombres=self.nombres_comprador,
                    apellidos=self.apellidos_comprador,
                    telefono=self.telefono_comprador,
                    email=self.email_comprador or '',
                    tipo_identificacion='CEDULA',
                    fuente_registro='WEB',
                )
        super().save(*args, **kwargs)

    @staticmethod
    def _generar_numero_orden():
        import random, string
        ultimo = PedidoOnline.objects.order_by('-id').first()
        num = (ultimo.id + 1) if ultimo else 1
        sufijo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"WEB-{num:05d}-{sufijo}"

    def get_nombre_comprador(self):
        return f"{self.nombres_comprador} {self.apellidos_comprador}".strip()

    def get_direccion_entrega(self):
        if self.tipo_entrega == 'RETIRO':
            return 'Retiro en tienda'
        parts = [self.direccion_envio or '']
        if self.ciudad_envio:
            parts.append(self.ciudad_envio)
        if self.provincia_envio:
            parts.append(self.provincia_envio)
        return ', '.join(p for p in parts if p)

    def tiene_comprobante(self):
        """Retorna True si tiene imagen de comprobante (base64 o archivo)"""
        return bool(self.comprobante_base64 or self.comprobante_transferencia)

    def get_comprobante_src(self):
        """
        Retorna el src listo para usar en un <img>.
        Prioriza base64 (API ecommerce), luego el archivo subido (legado).
        """
        if self.comprobante_base64 and self.comprobante_content_type:
            return f"data:{self.comprobante_content_type};base64,{self.comprobante_base64}"
        if self.comprobante_transferencia:
            return self.comprobante_transferencia.url
        return None

    # ══════════════════════════════════════════════════════════════
    #  MÉTODOS WHATSAPP
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def _normalizar_telefono_ec(telefono_raw):
        """
        Convierte cualquier formato de teléfono ecuatoriano al formato
        internacional requerido por WhatsApp (ej: 593991234567).

        Formatos aceptados:
          0991234567   → 593991234567  (móvil con 0 inicial)
          991234567    → 593991234567  (móvil sin 0)
          593991234567 → 593991234567  (ya tiene código de país)
          +593991234567→ 593991234567  (con signo +)
        """
        telefono = ''.join(filter(str.isdigit, telefono_raw or ''))
        if not telefono:
            return None
        if telefono.startswith('593') and len(telefono) >= 12:
            return telefono                          # ya tiene código de país
        if telefono.startswith('0') and len(telefono) == 10:
            return '593' + telefono[1:]              # 0991234567 → 593991234567
        if len(telefono) == 9:
            return '593' + telefono                  # 991234567  → 593991234567
        # Cualquier otro caso: devolver tal cual (no bloquear)
        return telefono

    def get_whatsapp_mensaje(self, numero_tienda='593XXXXXXXXX'):
        """Genera el mensaje prellenado para notificar a la TIENDA sobre un nuevo pedido"""
        items_texto = '\n'.join(
            f"  • {d.cantidad}x {d.nombre_producto} — ${d.total:.2f}"
            for d in self.detalles.all()
        )
        entrega = self.get_direccion_entrega()
        pago = self.get_metodo_pago_display()

        mensaje = (
            f"🛒 *NUEVO PEDIDO #{self.numero_orden}*\n\n"
            f"👤 *Cliente:* {self.get_nombre_comprador()}\n"
            f"🪪 *Cédula:* {self.cedula_comprador}\n"
            f"📱 *Teléfono:* {self.telefono_comprador}\n\n"
            f"📦 *Productos:*\n{items_texto}\n\n"
            f"💰 *Subtotal:* ${self.subtotal:.2f}\n"
            f"🚚 *Envío:* ${self.costo_envio:.2f}\n"
            f"💵 *TOTAL: ${self.total:.2f}*\n\n"
            f"🚚 *Entrega:* {entrega}\n"
            f"💳 *Pago:* {pago}\n\n"
            f"_Pedido realizado el {self.fecha_pedido.strftime('%d/%m/%Y %H:%M')}_"
        )
        return mensaje

    def get_whatsapp_url(self, numero_tienda):
        """
        URL de WhatsApp para que el CLIENTE contacte a la TIENDA.
        Usada al crear el pedido desde la tienda PHP.
        """
        import urllib.parse
        mensaje = self.get_whatsapp_mensaje(numero_tienda)
        return f"https://wa.me/{numero_tienda}?text={urllib.parse.quote(mensaje)}"

    def get_whatsapp_cliente_url(self):
        """
        URL de WhatsApp para que la TIENDA contacte al CLIENTE.
        Usada en el panel admin al gestionar el pedido.
        Retorna None si el pedido no tiene teléfono válido.
        """
        import urllib.parse
        telefono = self._normalizar_telefono_ec(self.telefono_comprador)
        if not telefono:
            return None

        mensaje = (
            f"Hola {self.nombres_comprador} 👋, le contactamos desde *GO MOTOS* "
            f"en relación a su pedido *#{self.numero_orden}* "
            f"por un total de *${self.total:.2f}*. ¿En qué le podemos ayudar?"
        )
        return f"https://wa.me/{telefono}?text={urllib.parse.quote(mensaje)}"

    # ══════════════════════════════════════════════════════════════

    def confirmar(self):
        self.estado = 'CONFIRMADO'
        self.fecha_confirmacion = timezone.now()
        self.save()

    def despachar(self, numero_guia=None):
        self.estado = 'DESPACHADO'
        self.fecha_despacho = timezone.now()
        if numero_guia:
            self.numero_guia = numero_guia
        self.save()

    def entregar(self):
        self.estado = 'ENTREGADO'
        self.fecha_entrega = timezone.now()
        self.save()

    def cancelar(self):
        """Cancela el pedido y revierte el stock"""
        if self.estado not in ('ENTREGADO', 'CANCELADO'):
            for detalle in self.detalles.all():
                if detalle.producto:
                    detalle.producto.stock_actual += detalle.cantidad
                    detalle.producto.save()
            self.estado = 'CANCELADO'
            self.save()
            return True
        return False


class DetallePedidoOnline(models.Model):
    """Líneas de un pedido online"""

    pedido = models.ForeignKey(PedidoOnline, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(
        'inventario.Producto', on_delete=models.PROTECT,
        null=True, blank=True
    )
    # Snapshot del producto al momento de la compra
    nombre_producto = models.CharField(max_length=200)
    codigo_producto = models.CharField(max_length=50, blank=True, null=True)
    imagen_producto = models.URLField(blank=True, null=True)

    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = _('Detalle Pedido Online')
        verbose_name_plural = _('Detalles Pedidos Online')

    def __str__(self):
        return f"{self.cantidad}x {self.nombre_producto} — Pedido #{self.pedido.numero_orden}"

    def save(self, *args, **kwargs):
        self.subtotal = self.precio_unitario * self.cantidad
        self.total = self.subtotal - self.descuento
        super().save(*args, **kwargs)


# ══════════════════════════════════════════════════════════════════════
#  MODELOS EXISTENTES (sin cambios)
# ══════════════════════════════════════════════════════════════════════

class MovimientoPuntos(models.Model):
    TIPO_MOVIMIENTO_CHOICES = [
        ('GANADO', 'Puntos Ganados'),
        ('CANJEADO', 'Puntos Canjeados'),
        ('AJUSTE', 'Ajuste Manual'),
        ('VENCIDO', 'Puntos Vencidos'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='movimientos_puntos')
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO_CHOICES)
    puntos = models.PositiveIntegerField()
    concepto = models.CharField(max_length=200)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    venta = models.ForeignKey('ventas.Venta', on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        verbose_name = _('Movimiento de Puntos')
        verbose_name_plural = _('Movimientos de Puntos')
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.cliente.get_nombre_completo()} - {self.tipo} - {self.puntos} puntos"


class ConfiguracionPuntos(models.Model):
    REGLA_CHOICES = [
        ('POR_DOLAR', 'Puntos por dólar gastado'),
        ('POR_VENTA', 'Puntos por venta realizada'),
        ('POR_REFERIDO', 'Puntos por cliente referido'),
    ]

    nombre = models.CharField(max_length=100)
    regla = models.CharField(max_length=20, choices=REGLA_CHOICES)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)
    fecha_inicio = models.DateField(default=timezone.now)
    fecha_fin = models.DateField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _('Configuración de Puntos')
        verbose_name_plural = _('Configuraciones de Puntos')

    def __str__(self):
        return f"{self.nombre} - {self.get_regla_display()}"

    @classmethod
    def calcular_puntos_venta(cls, total_venta):
        configuraciones = cls.objects.filter(
            activo=True,
            fecha_inicio__lte=timezone.now().date()
        ).filter(
            models.Q(fecha_fin__isnull=True) |
            models.Q(fecha_fin__gte=timezone.now().date())
        )
        total_puntos = 0
        for config in configuraciones:
            if config.regla == 'POR_DOLAR':
                total_puntos += int(total_venta * config.valor)
            elif config.regla == 'POR_VENTA':
                total_puntos += int(config.valor)
        return total_puntos


class CanjeoPuntos(models.Model):
    TIPO_PREMIO_CHOICES = [
        ('DESCUENTO', 'Descuento en compra'),
        ('SERVICIO_GRATIS', 'Servicio gratuito'),
        ('PRODUCTO_GRATIS', 'Producto gratuito'),
        ('OTRO', 'Otro premio'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='canjes')
    tipo_premio = models.CharField(max_length=20, choices=TIPO_PREMIO_CHOICES)
    descripcion_premio = models.CharField(max_length=200)
    puntos_utilizados = models.PositiveIntegerField()
    valor_equivalente = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fecha_canje = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)
    utilizado = models.BooleanField(default=False)
    fecha_utilizacion = models.DateTimeField(blank=True, null=True)
    venta_utilizacion = models.ForeignKey('ventas.Venta', on_delete=models.SET_NULL,
                                          blank=True, null=True, related_name='canjes_utilizados')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = _('Canje de Puntos')
        verbose_name_plural = _('Canjes de Puntos')
        ordering = ['-fecha_canje']

    def __str__(self):
        return f"{self.cliente.get_nombre_completo()} - {self.descripcion_premio}"

    def marcar_como_utilizado(self, venta=None):
        self.utilizado = True
        self.fecha_utilizacion = timezone.now()
        self.venta_utilizacion = venta
        self.save()


class Moto(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='motos')
    placa = models.CharField(max_length=20, unique=True)
    marca = models.ForeignKey('inventario.Marca', on_delete=models.CASCADE)
    modelo = models.CharField(max_length=100)
    año = models.CharField(max_length=4)
    color = models.CharField(max_length=50)
    numero_chasis = models.CharField(max_length=50, blank=True, null=True)
    numero_motor = models.CharField(max_length=50, blank=True, null=True)
    cilindraje = models.CharField(max_length=20, blank=True, null=True)
    tipo = models.CharField(max_length=50, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, default='Activo')
    kilometraje = models.PositiveIntegerField(blank=True, null=True)
    fecha_ultima_revision = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = _('Moto')
        verbose_name_plural = _('Motos')
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"{self.marca} {self.modelo} - {self.placa} ({self.cliente.nombres})"




class HistorialCliente(models.Model):
    TIPO_INTERACCION_CHOICES = [
        ('VENTA', 'Venta realizada'),
        ('PEDIDO_ONLINE', 'Pedido online'),
        ('SERVICIO', 'Servicio prestado'),
        ('LLAMADA', 'Llamada telefónica'),
        ('EMAIL', 'Email enviado'),
        ('WHATSAPP', 'Mensaje WhatsApp'),
        ('VISITA', 'Visita al taller'),
        ('RECLAMO', 'Reclamo o queja'),
        ('FELICITACION', 'Felicitación'),
        ('OTRO', 'Otro tipo'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='historial')
    tipo = models.CharField(max_length=20, choices=TIPO_INTERACCION_CHOICES)
    descripcion = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    venta = models.ForeignKey('ventas.Venta', on_delete=models.SET_NULL, blank=True, null=True)
    pedido_online = models.ForeignKey(PedidoOnline, on_delete=models.SET_NULL, blank=True, null=True)

    importante = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('Historial de Cliente')
        verbose_name_plural = _('Historiales de Clientes')
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.cliente.get_nombre_completo()} - {self.get_tipo_display()}"