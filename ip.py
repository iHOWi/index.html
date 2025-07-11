import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import time
from datetime import datetime, time as dt_time
import pytz
import random

# Список русских ругательств
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
    "Лаваш гавядина твая мамка блядина"
    "Ебать ты долбаеб, бота пытается он затролить 🤣", 
    "Пиздюк, иди нахуй пожалуйста",
]

# IMPORTANT: Replace with your actual bot token
TOKEN = "8009426826:AAHgd0hmxREuMxSnm2HDkyyF62CIRVRtrlk" # Please ensure this is your correct token
CHANNEL_ID = "@ip_searcher"  # Замените на username вашего канала

# "База данных" для хранения данных пользователей (в реальном проекте используйте БД)
users_db = {
    # user_id: {
    #     'referrals': set(),  # рефералы пользователя
    #     'tokens': 5,         # начальное количество токенов
    #     'last_check': None,  # последняя проверка на ежедневные токены
    #     'referrer': None     # кто пригласил этого пользователя
    # }
}

async def handle_insults(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ругательства и отвечает грубо"""
    user_message = update.message.text.lower()
    
    # Проверяем, содержит ли сообщение ругательство
    for insult in RUSSIAN_INSULTS:
        if insult in user_message:
            response = random.choice(RUDE_RESPONSES)
            await update.message.reply_text(response)
            return True
    
    return False

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if a user is subscribed to the specified channel.
    """
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

async def update_tokens_daily():
    """
    Updates daily tokens for users.
    Users get 3 tokens if their current tokens are less than 5, once per day after midnight MSK.
    """
    moscow_tz = pytz.timezone('Europe/Moscow')
    now = datetime.now(moscow_tz)
    
    for user_id, user_data in users_db.items():
        last_check = user_data.get('last_check')
        
        # Check if it's a new day since the last check
        if not last_check or (now.date() > last_check.date()):
            # Award tokens only if current tokens are less than 5
            if user_data['tokens'] < 5:
                user_data['tokens'] += 3
                if user_data['tokens'] > 5: # Cap at 5 tokens
                    user_data['tokens'] = 5
            user_data['last_check'] = now

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /start command, initializes user data, checks referrals, and subscription.
    """
    user_id = update.effective_user.id
    
    # Initialize user in the database if not exists
    if user_id not in users_db:
        users_db[user_id] = {
            'referrals': set(),
            'tokens': 5,
            'last_check': None,
            'referrer': None
        }
    
    # Process referral link if provided
    if context.args:
        try:
            referrer_id = int(context.args[0])
            # Ensure referrer is not the user themselves and exists in DB, and user hasn't been referred before
            if referrer_id != user_id and referrer_id in users_db and users_db[user_id]['referrer'] is None:
                users_db[user_id]['referrer'] = referrer_id
                users_db[referrer_id]['referrals'].add(user_id)
                
                # Award 3 tokens to the referrer
                users_db[referrer_id]['tokens'] += 3
                if users_db[referrer_id]['tokens'] > 100: # Cap referral tokens to prevent abuse
                    users_db[referrer_id]['tokens'] = 100 
                # Notify referrer about new referral
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 У вас новый реферал! Пользователь {update.effective_user.first_name} присоединился по вашей ссылке. "
                         f"Вы получили +3 запроса. Текущий баланс: {users_db[referrer_id]['tokens']} запросов."
                )
        except (ValueError, KeyError):
            pass # Ignore invalid referrer IDs
    
    # Check channel subscription
    is_subscribed = await check_subscription(user_id, context)
    
    if not is_subscribed:
        await update.message.reply_text(
            "📢 Для использования бота необходимо подписаться на наш канал!\n\n"
            "После подписки нажмите кнопку ниже:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                [InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')]
            ])
        )
        return
    
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the main menu to the user.
    Handles both initial message and callback query edits.
    """
    # Determine the user based on whether it's a Message or CallbackQuery
    if isinstance(update, Update) and update.callback_query:
        # If update has a callback_query (meaning it's from a button press)
        user_id = update.callback_query.from_user.id
        user_first_name = update.callback_query.from_user.first_name
        message_to_edit = update.callback_query.message
    else: 
        # If update is a Message (e.g., from /start command or direct text input)
        user_id = update.effective_user.id
        user_first_name = update.effective_user.first_name
        message_to_edit = update.message
    
    # Update tokens before showing the menu
    await update_tokens_daily()
    
    keyboard = [
        [InlineKeyboardButton("🔍 Проверить IP", callback_data='check_ip')],
        [InlineKeyboardButton("📊 Рефералы", callback_data='referrals')],
        [InlineKeyboardButton("⚙️ Настройки", callback_data='settings')],
        [InlineKeyboardButton("📢 Наш канал", url=f"https://t.me/{CHANNEL_ID[1:]}")]
    ]
    
    text = (
        f"👋 <b>Привет, {user_first_name}!</b>\n\n" 
        "Я бот для проверки IP-адресов\n\n"
        f"<b>Ваш ID:</b> <code>{user_id}</code>\n"
        f"<b>Доступные запросы:</b> {users_db[user_id]['tokens']}\n\n"
        f"<b>Реферальная ссылка:</b>\n"
        f"<code>https://t.me/{(await context.bot.get_me()).username}?start={user_id}</code>\n\n"
        "За каждого приглашенного друга вы получаете +3 запроса!"
    )
    
    # Now, use the message_to_edit or update.message correctly
    if isinstance(update, Update) and update.callback_query:
        await message_to_edit.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else: 
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles all inline keyboard button presses.
    """
    query = update.callback_query
    await query.answer() # Acknowledge the callback query
    
    user_id = query.from_user.id
    
    if query.data == 'check_subscription':
        is_subscribed = await check_subscription(user_id, context)
        
        if is_subscribed:
            # Pass the original 'query' object (which is an Update type with a callback_query)
            await show_main_menu(update, context) 
        else:
            await query.edit_message_text(
                "❌ Вы еще не подписались на канал! Пожалуйста, подпишитесь и попробуйте снова.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                    [InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')]
                ])
            )
    
    elif query.data == 'check_ip':
        if users_db[user_id]['tokens'] <= 0:
            await query.edit_message_text(
                "❌ У вас закончились доступные запросы!\n\n"
                "Вы можете:\n"
                "1. Пригласить друзей по реферальной ссылке (+3 запроса за каждого)\n"
                "2. Подождать до завтра (ежедневно начисляется +3 запроса, если у вас меньше 5)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 Рефералы", callback_data='referrals')],
                    [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
                ])
            )
            return
        
        await query.edit_message_text(
            "📝 Введите IP-адрес или домен для проверки:",
            parse_mode="HTML"
        )
        context.user_data['waiting_for_ip'] = True
        
    elif query.data == 'referrals':
        # Check channel subscription for referral page access
        is_subscribed = await check_subscription(user_id, context)
        if not is_subscribed:
            await query.edit_message_text(
                "❌ Для просмотра рефералов необходимо подписаться на канал!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                    [InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')]
                ])
            )
            return
        
        ref_count = len(users_db[user_id]['referrals'])
        
        await query.edit_message_text(
            f"📊 <b>Ваша реферальная статистика:</b>\n\n"
            f"• Всего рефералов: <b>{ref_count}</b>\n"
            f"• Доступные запросы: <b>{users_db[user_id]['tokens']}</b>\n\n"
            f"<b>Реферальная ссылка:</b>\n"
            f"<code>https://t.me/{(await context.bot.get_me()).username}?start={user_id}</code>\n\n"
            "За каждого реферала, который подписался на канал, вы получаете +3 запроса!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
            ])
        )
    
    elif query.data == 'settings':
        await query.edit_message_text(
            "⚙️ <b>Настройки бота:</b>\n\n"
            "Здесь будут настройки, когда я их добавлю 😊",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
            ])
        )
    
    elif query.data == 'back_to_main':
        # Pass the original 'update' object (which is a CallbackQuery type)
        await show_main_menu(update, context) 

def get_ip_info(ip: str) -> str:
    """
    Fetches IP information from ip-api.com.
    """
    url = f"http://ip-api.com/json/{ip}?fields=66846719&lang=ru"
    try:
        response = requests.get(url, timeout=5).json() 
    except requests.exceptions.RequestException as e:
        return f"❌ <b>Ошибка подключения:</b> {e}"
    
    if response.get("status") == "fail":
        return f"❌ <b>Ошибка:</b> {response.get('message')}"
    
    info = f"""
🔍 <b>Информация о</b> <code>{response.get('query', 'N/A')}</code>:

<b>📍 Локация:</b>
• <i>Страна:</i> {response.get('country', 'N/A')} ({response.get('countryCode', 'N/A')})
• <i>Регион:</i> {response.get('regionName', 'N/A')}
• <i>Город:</i> {response.get('city', 'N/A')}
• <i>Почтовый индекс:</i> {response.get('zip', 'N/A')}
• <i>Координаты:</i> {response.get('lat', 'N/A')}, {response.get('lon', 'N/A')}

<b>🌐 Сеть:</b>
• <i>Провайдер:</i> {response.get('isp', 'N/A')}
• <i>Организация:</i> {response.get('org', 'N/A')}
• <i>AS:</i> {response.get('as', 'N/A')}

<b>⏰ Время:</b>
• <i>Часовой пояс:</i> {response.get('timezone', 'N/A')}

<b>🔒 Безопасность:</b>
• <i>Прокси/VPN:</i> {'✅ Да' if response.get('proxy') or response.get('hosting') else '❌ Нет'}
"""
    return info.strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles incoming text messages, primarily for IP checking.
    """
    # Сначала проверяем на ругательства
    if await handle_insults(update, context):
        return
    
    user_id = update.effective_user.id
    
    # Check channel subscription for any message
    is_subscribed = await check_subscription(user_id, context)
    if not is_subscribed:
        await update.message.reply_text(
            "❌ Для использования бота необходимо подписаться на наш канал!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_ID[1:]}")],
                [InlineKeyboardButton("✅ Я подписался", callback_data='check_subscription')]
            ])
        )
        return
    
    if context.user_data.get('waiting_for_ip'):
        user_input = update.message.text.strip()
        
        if not user_input:
            await update.message.reply_text("❌ <b>Пожалуйста, введите IP-адрес или домен!</b>", parse_mode="HTML")
            return
        
        # Check token count
        if users_db[user_id]['tokens'] <= 0:
            await update.message.reply_text(
                "❌ У вас закончились доступные запросы!\n\n"
                "Вы можете:\n"
                "1. Пригласить друзей по реферальной ссылке (+3 запроса за каждого)\n"
                "2. Подождать до завтра (ежедневно начисляется +3 запроса, если у вас меньше 5)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 Рефералы", callback_data='referrals')],
                    [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
                ])
            )
            del context.user_data['waiting_for_ip']
            return
        
        await update.message.reply_text("⏳ <i>Запрашиваю информацию...</i>", parse_mode="HTML")
        
        try:
            ip_info = get_ip_info(user_input)
            
            # Проверяем, была ли ошибка в ответе от API
            if ip_info.startswith("❌"):
                # При ошибке НЕ списываем токены
                await update.message.reply_text(
                    ip_info,
                    parse_mode="HTML",
                    reply_to_message_id=update.message.message_id
                )
            else:
                # Токены списываем только при успешном запросе
                users_db[user_id]['tokens'] -= 1
                await update.message.reply_text(
                    ip_info + f"\n\n<b>Осталось запросов:</b> {users_db[user_id]['tokens']}",
                    parse_mode="HTML",
                    reply_to_message_id=update.message.message_id
                )
                
        except Exception as e:
            # При любых других ошибках тоже не списываем токены
            await update.message.reply_text(
                f"❌ <b>Ошибка:</b> {str(e)}",
                parse_mode="HTML",
                reply_to_message_id=update.message.message_id
            )
        
        del context.user_data['waiting_for_ip']
        await show_main_menu_after_action(update, context)
    else:
        await update.message.reply_text("ℹ️ Используйте кнопки для взаимодействия с ботом")

async def show_main_menu_after_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the main menu after an action (like IP check).
    Always uses reply_text for this specific scenario as it's a new message after user input.
    """
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("🔍 Проверить IP", callback_data='check_ip')],
        [InlineKeyboardButton("📊 Рефералы", callback_data='referrals')],
        [InlineKeyboardButton("⚙️ Настройки", callback_data='settings')],
        [InlineKeyboardButton("📢 Наш канал", url=f"https://t.me/{CHANNEL_ID[1:]}")]
    ]
    
    text = (
        "🔹 <b>Главное меню</b> 🔹\n\n"
        f"<b>Доступные запросы:</b> {users_db[user_id]['tokens']}\n\n"
        "Выберите действие:"
    )
    
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    """
    Main function to set up and run the Telegram bot.
    """
    app = Application.builder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run the bot
    print("Bot started polling...")
    app.run_polling(poll_interval=1.0) 

if __name__ == "__main__":
    main()