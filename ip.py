import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import pytz
from datetime import datetime
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Конфиг
TOKEN = os.getenv("TOKEN", "8009426826:AAHgd0hmxREuMxSnm2HDkyyF62CIRVRtrlk")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@ip_searcher")
PORT = int(os.getenv("PORT", 10000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://ipsearchur-ru.onrender.com/8009426826:AAHgd0hmxREuMxSnm2HDkyyF62CIRVRtrlk")

# База данных
users_db = {}

### Обработчики сообщений ###
RUSSIAN_INSULTS = [
    "пидр", "пидор", "пидорас", "хуесос", "сука", "скотина", 
    "пиздюк", "уебан", "долбаеб", "мудак", "гандон", "дебил",
    "тупой", "лох", "чмо", "долбоеб", "придурок", "кретин",
    "идиот", "дурак", "тупица", "засранец", "сучка", "мразь",
    "падла", "сволочь", "ублюдок", "выблядок", "жопа", "говно", "пошел нахуй", "пидорас ебаный", "мать", "мамка", "шлюха", "мать шлюха"
]

# Грубые ответы на оскорбления
RUDE_RESPONSES = [
    "Ты не лучше, кусок говна",
    "пошел нахуй, уёбище",
    "Пошел нахуй, дебил",
    "Заткнись, долбаеб",
    "Ты мне🤣🤣 ? Да ты сам полное дерьмо",
    "Валяй отсюда, мразь",
    "Я б тебе ответил, но ты того не стоишь, мудила",
    "Ты вообще кто такой, говноед?",
    "Иди в пень, урод",
    "Закрой рот, пока зубов не лишился, мудила",
    "Лаваш гавядина твая мамка блядина",
    "Ебать ты долбаеб, бота пытается он затролить 🤣", 
    "Пиздюк, иди нахуй пожалуйста"
]

async def handle_insults(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ на маты"""
    user_message = update.message.text.lower()
    if any(insult in user_message for insult in RUSSIAN_INSULTS):
        await update.message.reply_text(random.choice(RUDE_RESPONSES))
        return True
    return False

### Основное меню ###
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 Проверить IP", callback_data='check_ip')],
        [InlineKeyboardButton("📊 Рефералы", callback_data='referrals')],
        [InlineKeyboardButton("📢 Наш канал", url=f"https://t.me/{CHANNEL_ID[1:]}")]
    ]
    
    user = update.effective_user
    text = (
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        "Я бот для проверки IP-адресов\n\n"
        f"<b>Ваш ID:</b> <code>{user.id}</code>\n"
        f"<b>Запросы:</b> {users_db.get(user.id, {}).get('tokens', 5)}"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

### Проверка IP ###
def get_ip_info(ip: str) -> str:
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}?fields=66846719&lang=ru", timeout=5).json()
        if response["status"] == "fail":
            return f"❌ Ошибка: {response['message']}"
            
        return f"""
🔍 <b>Информация о IP:</b>
<b>Страна:</b> {response.get('country', 'N/A')}
<b>Город:</b> {response.get('city', 'N/A')}
<b>Провайдер:</b> {response.get('isp', 'N/A')}
"""
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

### Обработчики команд ###
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users_db:
        users_db[user_id] = {'tokens': 5, 'referrals': set()}
    await show_main_menu(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'check_ip':
        if users_db[query.from_user.id]['tokens'] <= 0:
            await query.edit_message_text("❌ Нет доступных запросов!")
            return
        await query.edit_message_text("Введите IP-адрес:")
        context.user_data['waiting_for_ip'] = True
        
    elif query.data == 'referrals':
        ref_link = f"https://t.me/{(await context.bot.get_me()).username}?start={query.from_user.id}"
        await query.edit_message_text(
            f"📊 Ваши рефералы: {len(users_db[query.from_user.id]['referrals'])}\n"  # <- Закрывающая скобка для len()
            f"🔗 Ваша ссылка:\n{ref_link}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='back')]])
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_insults(update, context):
        return
        
    if context.user_data.get('waiting_for_ip'):
        ip_info = get_ip_info(update.message.text)
        if not ip_info.startswith("❌"):
            users_db[update.effective_user.id]['tokens'] -= 1
        await update.message.reply_text(ip_info, parse_mode="HTML")
        await show_main_menu(update, context)

### Health-сервер для Render ###
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    server.serve_forever()

### Запуск ###
def main():
    # Health-сервер
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # Бот
    app = Application.builder().token(TOKEN).build()
    
    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Webhook или Polling
    if WEBHOOK_URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
