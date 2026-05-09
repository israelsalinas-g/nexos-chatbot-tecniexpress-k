"""
Handler de búsqueda visual por imagen para el bot de Telegram.
Se integra con tu bot existente sin tocar el flujo de texto.
"""

import base64
import io
import logging
from typing import Optional

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from app.config import get_settings

logger = logging.getLogger(__name__)

# Estados del conversation handler (si quieres flujo interactivo)
SELECTING_PRODUCT, CONFIRMING_QUOTE = range(2)

VISUAL_SEARCH_API = "http://localhost:8000/api/v1/search/by-image"
# En producción: VISUAL_SEARCH_API = "https://tu-api.com/api/v1/search/by-image"


async def handle_photo_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler principal cuando el usuario envía una foto.
    Se registra como: MessageHandler(filters.PHOTO, handle_photo_search)
    """
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Obtener el tipo de cliente desde tu base de datos (o usar 'public' por defecto)
    customer_type = await get_customer_type(chat_id) or "public"
    
    # Enviar mensaje de "procesando"
    processing_msg = await update.message.reply_text(
        "🔍 Analizando imagen y buscando en catálogo... esto tomará unos segundos."
    )
    
    try:
        # 1. Descargar la foto de mejor calidad
        photo = update.message.photo[-1]  # Último = mejor resolución
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Validar tamaño (máx 5MB)
        if len(photo_bytes) > 5 * 1024 * 1024:
            await processing_msg.edit_text(
                "❌ La imagen es muy grande. Por favor envía una foto menor a 5MB."
            )
            return
        
        # 2. Convertir a base64
        image_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        # 3. Llamar a la API de búsqueda visual
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                VISUAL_SEARCH_API,
                json={
                    "image_base64": image_base64,
                    "customer_type": customer_type,
                    "max_results": 5
                }
            )
            response.raise_for_status()
            result = response.json()
        
        # 4. Procesar resultado según tipo
        await processing_msg.delete()
        
        if result["result_type"] == "direct_match":
            await send_direct_match(update, context, result, customer_type)
        elif result["result_type"] == "multiple_options":
            await send_multiple_options(update, context, result, customer_type)
        else:
            await send_no_match(update, context, result)
            
    except httpx.ConnectError:
        await processing_msg.edit_text(
            "⚠️ Servicio de búsqueda visual no disponible. "
            "Por favor intenta más tarde o escribe el nombre del repuesto."
        )
    except Exception as e:
        logger.error(f"Error en búsqueda visual: {e}", exc_info=True)
        await processing_msg.edit_text(
            "❌ Ocurrió un error procesando la imagen. "
            "Por favor intenta de nuevo o escribe el nombre del repuesto."
        )


async def send_direct_match(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    result: dict,
    customer_type: str
):
    """Envía resultado cuando hay coincidencia directa (>85% confianza)."""
    
    product = result["products"][0]
    price = product["price_public"]  # Ya viene filtrado por customer_type desde la API
    
    # Construir mensaje
    message = (
        f"✅ *¡Encontré tu repuesto!*\n\n"
        f"*{product['name_es']}*\n"
        f"{'📝 ' + product['name_en'] + chr(10) if product.get('name_en') else ''}"
        f"🔧 SKU: `{product['sku']}`\n"
    )
    
    if product.get("part_number"):
        message += f"🔩 No. Parte: `{product['part_number']}`\n"
    
    message += (
        f"🏷️ Marca: {product.get('brand_name', 'N/A')}\n"
        f"📂 Categoría: {product.get('category_name', 'N/A')}\n"
        f"🎯 Confianza: {product['confidence_percent']}%\n\n"
        f"💰 *Precio: L. {price:,}*\n"
        f"📦 Stock disponible: {product['stock_quantity']} unidades\n\n"
        f"¿Deseas agregarlo al carrito?"
    )
    
    # Botones de acción
    keyboard = [
        [
            InlineKeyboardButton(
                "🛒 Agregar al carrito", 
                callback_data=f"add_cart:{product['product_id']}"
            ),
            InlineKeyboardButton(
                "🔍 Ver detalles", 
                callback_data=f"product:{product['product_id']}"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Ver otros resultados", 
                callback_data="see_more_results"
            )
        ]
    ]
    
    # Enviar foto del producto encontrado
    await update.message.reply_photo(
        photo=product["image_url"],
        caption=message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Guardar en contexto para referencia posterior
    context.user_data["last_search_results"] = result["products"]
    context.user_data["selected_product"] = product


async def send_multiple_options(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE, 
    result: dict,
    customer_type: str
):
    """Envía opciones múltiples cuando la confianza es media (70-85%)."""
    
    message = (
        "🔍 Encontré estas posibles coincidencias.\n"
        "*¿Cuál de estos es el repuesto que buscas?*\n\n"
    )
    
    keyboard = []
    
    for i, product in enumerate(result["products"][:3], 1):
        price = product["price_public"]
        
        message += (
            f"{i}. *{product['name_es']}*\n"
            f"   Confianza: {product['confidence_percent']}% | "
            f"L. {price:,} | Stock: {product['stock_quantity']}\n\n"
        )
        
        keyboard.append([
            InlineKeyboardButton(
                f"{i}. {product['name_es'][:30]}...",
                callback_data=f"select_product:{product['product_id']}"
            )
        ])
    
    # Opciones adicionales
    keyboard.append([
        InlineKeyboardButton(
            "❌ Ninguno de estos", 
            callback_data="no_match_found"
        )
    ])
    keyboard.append([
        InlineKeyboardButton(
            "📷 Enviar otra foto", 
            callback_data="send_another_photo"
        )
    ])
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Guardar resultados para callback
    context.user_data["last_search_results"] = result["products"]


async def send_no_match(update: Update, context: ContextTypes.DEFAULT_TYPE, result: dict):
    """Maneja cuando no hay coincidencias claras."""
    
    message = (
        "❌ *No encontré coincidencias claras* con esa imagen.\n\n"
        "Esto puede deberse a:\n"
        "• Mala iluminación o foto borrosa\n"
        "• El repuesto no está en nuestro catálogo\n"
        "• Ángulo de foto no permite identificar bien\n\n"
        "*¿Qué puedes hacer?*"
    )
    
    keyboard = [
        [InlineKeyboardButton("📷 Enviar otra foto", callback_data="retry_photo")],
        [InlineKeyboardButton("⌨️ Escribir nombre del repuesto", callback_data="search_text")],
        [InlineKeyboardButton("🔧 Indicar marca/modelo", callback_data="ask_model")],
    ]
    
    # Si hay alternativas del API, mostrarlas
    if result.get("alternatives"):
        for alt in result["alternatives"]:
            # Mapear alternativas a botones según contenido
            if "ángulo" in alt.lower():
                keyboard.insert(0, [InlineKeyboardButton(f"🔄 {alt}", callback_data="retry_photo")])
    
    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================
# CALLBACK HANDLERS (para los botones)
# ============================================

async def handle_product_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cuando el usuario selecciona un producto de las opciones múltiples."""
    query = update.callback_query
    await query.answer()
    
    product_id = query.data.split(":")[1]
    products = context.user_data.get("last_search_results", [])
    
    # Buscar producto seleccionado
    selected = next((p for p in products if str(p["product_id"]) == product_id), None)
    
    if not selected:
        await query.edit_message_text("❌ Producto no encontrado. Intenta de nuevo.")
        return
    
    # Mostrar detalle del producto seleccionado como si fuera match directo
    await query.message.reply_photo(
        photo=selected["image_url"],
        caption=(
            f"✅ *Seleccionaste:*\n\n"
            f"*{selected['name_es']}*\n"
            f"🔧 SKU: `{selected['sku']}`\n"
            f"💰 Precio: L. {selected['price_public']:,}\n"
            f"📦 Stock: {selected['stock_quantity']}\n\n"
            f"¿Deseas agregarlo al carrito?"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🛒 Agregar al carrito",
                callback_data=f"add_cart:{selected['product_id']}"
            )
        ]])
    )


async def handle_add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Integración con tu carrito existente."""
    query = update.callback_query
    await query.answer()
    
    product_id = query.data.split(":")[1]
    
    # Aquí integras con tu lógica de carrito existente
    # Por ejemplo, llamar a tu API interna de órdenes
    
    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Agregado", callback_data="done")
        ]])
    )
    
    await query.message.reply_text(
        "🛒 Producto agregado a tu carrito.\n"
        "¿Deseas:\n"
        "/carrito - Ver carrito\n"
        "/buscar - Buscar más repuestos\n"
        "/finalizar - Finalizar compra"
    )


# ============================================
# AUXILIAR: Obtener tipo de cliente desde BD
# ============================================

async def get_customer_type(chat_id: int) -> Optional[str]:
    """Obtiene el tipo de cliente desde tu tabla de perfiles/telegram_sessions."""
    # Integrar con tu base de datos existente
    # Por ahora retorna None para usar 'public' por defecto
    return None


# ============================================
# REGISTRO EN TU BOT PRINCIPAL
# ============================================

def register_visual_search_handlers(application):
    """
    Llama esta función en tu main.py del bot para registrar handlers.
    
    Ejemplo:
        from telegram.ext import Application, MessageHandler, filters
        from handlers.visual_search import register_visual_search_handlers
        
        app = Application.builder().token(TOKEN).build()
        register_visual_search_handlers(app)
    """
    from telegram.ext import CallbackQueryHandler
    
    # Handler para fotos (debe ir ANTES del handler de texto genérico)
    application.add_handler(
        MessageHandler(filters.PHOTO, handle_photo_search)
    )
    
    # Callbacks para botones de selección
    application.add_handler(
        CallbackQueryHandler(handle_product_selection, pattern=r"^select_product:")
    )
    application.add_handler(
        CallbackQueryHandler(handle_add_to_cart, pattern=r"^add_cart:")
    )
    
    # Otros callbacks útiles
    application.add_handler(
        CallbackQueryHandler(
            lambda u, c: u.callback_query.message.reply_text("Envía la nueva foto:"),
            pattern="^retry_photo$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            lambda u, c: u.callback_query.message.reply_text("Escribe el nombre o SKU del repuesto:"),
            pattern="^search_text$"
        )
    )