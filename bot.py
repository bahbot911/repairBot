import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import db

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Инициализация бота
API_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ============= КЛАВИАТУРЫ =============

def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton('➕ Новый ремонт'),
        types.KeyboardButton('📋 Активные ремонты'),
        types.KeyboardButton('✅ Завершённые'),
        types.KeyboardButton('📊 Статистика'),
        types.KeyboardButton('🔍 Поиск по номеру')
    ]
    keyboard.add(*buttons)
    return keyboard

# ============= ОБРАБОТЧИКИ КОМАНД =============

@dp.message_handler(commands=['start', 'help'])
async def cmd_start(message: types.Message):
    """Обработка команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Проверка в белом списке
    if not db.is_user_whitelisted(user_id):
        # Для первого запуска — добавим первого пользователя автоматически
        # В реальном проекте убираем эту автоматическую добавку
        if db.add_to_whitelist(user_id, username):
            await message.answer(
                "👋 Привет! Я бот для учёта ремонтов автомобилей.\n\n"
                "Доступные команды:\n"
                "➕ Новый ремонт - добавить новый ремонт\n"
                "📋 Активные ремонты - посмотреть текущие ремонты\n"
                "✅ Завершённые - завершённые ремонты\n"
                "📊 Статистика - статистика по ремонтам\n"
                "🔍 Поиск по номеру - найти все ремонты по госномеру",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer("❌ Ошибка добавления в белый список. Обратитесь к администратору.")
        return
    
    await message.answer(
        "👋 Привет! Я бот для учёта ремонтов автомобилей.\n\n"
        "Доступные команды:\n"
        "➕ Новый ремонт - добавить новый ремонт\n"
        "📋 Активные ремонты - посмотреть текущие ремонты\n"
        "✅ Завершённые - завершённые ремонты\n"
        "📊 Статистика - статистика по ремонтам\n"
        "🔍 Поиск по номеру - найти все ремонты по госномеру",
        reply_markup=get_main_keyboard()
    )

@dp.message_handler(lambda message: message.text == '➕ Новый ремонт')
async def add_repair_start(message: types.Message):
    """Начало добавления нового ремонта"""
    await message.answer(
        "📝 Введите данные ремонта в формате:\n\n"
        "Номер машины\n"
        "Модель (опционально)\n"
        "Описание работ\n"
        "Мастер (опционально)\n\n"
        "Пример:\n"
        "А123ВВ77\n"
        "Toyota Camry\n"
        "Замена масла и фильтров\n"
        "Иван Петров"
    )
    # Устанавливаем состояние
    dp['state'] = {'action': 'add_repair', 'user_id': message.from_user.id}

@dp.message_handler(lambda message: dp.get('state', {}).get('action') == 'add_repair')
async def add_repair_process(message: types.Message):
    """Обработка ввода данных нового ремонта"""
    lines = message.text.strip().split('\n')
    
    if len(lines) < 2:
        await message.answer("❌ Пожалуйста, введите как минимум номер и описание.")
        return
    
    car_number = lines[0].strip()
    car_model = lines[1].strip() if len(lines) > 1 else None
    description = lines[2].strip() if len(lines) > 2 else "Нет описания"
    master = lines[3].strip() if len(lines) > 3 else None
    
    try:
        repair_id = db.add_repair(car_number, description, car_model, master, message.from_user.id)
        
        await message.answer(
            f"✅ Ремонт добавлен!\n\n"
            f"🆔 ID: {repair_id}\n"
            f"🚗 Номер: {car_number}\n"
            f"📝 Описание: {description}\n"
            f"👨‍🔧 Мастер: {master or 'Не указан'}\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении ремонта: {str(e)}")
    
    dp['state'] = {}

@dp.message_handler(lambda message: message.text == '📋 Активные ремонты')
async def show_active_repairs(message: types.Message):
    """Показать активные ремонты"""
    repairs = db.get_all_repairs(status='в работе', limit=20)
    
    if not repairs:
        await message.answer("🔆 Активных ремонтов нет.", reply_markup=get_main_keyboard())
        return
    
    text = "📋 *Активные ремонты:*\n\n"
    for r in repairs:
        text += (
            f"🆔 #{r['id']}\n"
            f"🚗 {r['car_number']} {r['car_model'] or ''}\n"
            f"📝 {r['description'][:40]}{'...' if len(r['description']) > 40 else ''}\n"
            f"👨‍🔧 {r['master'] or 'Не указан'}\n"
            f"📅 {r['created_at'].strftime('%d.%m.%Y %H:%M')}\n"
            f"---\n"
        )
    
    # Добавляем кнопки для завершения
    keyboard = InlineKeyboardMarkup(row_width=2)
    for r in repairs[:5]:  # максимум 5 кнопок
        keyboard.add(InlineKeyboardButton(
            f"✅ Завершить #{r['id']}", 
            callback_data=f"complete_{r['id']}"
        ))
    
    await message.answer(text, reply_markup=keyboard, parse_mode='Markdown')

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('complete_'))
async def process_complete_callback(callback_query: types.CallbackQuery):
    """Обработка завершения ремонта по кнопке"""
    await bot.answer_callback_query(callback_query.id)
    
    repair_id = int(callback_query.data.split('_')[1])
    repair = db.get_repair(repair_id)
    
    if not repair:
        await bot.send_message(callback_query.from_user.id, "❌ Ремонт не найден")
        return
    
    # Запрашиваем стоимость
    msg = await bot.send_message(
        callback_query.from_user.id,
        f"💰 Введите стоимость ремонта #{repair_id}:\n"
        f"(например: 5000 или 5000.50)\n\n"
        f"🚗 {repair['car_number']}\n"
        f"📝 {repair['description']}"
    )
    
    # Сохраняем состояние
    dp['state'] = {
        'action': 'complete_repair',
        'repair_id': repair_id,
        'user_id': callback_query.from_user.id
    }

@dp.message_handler(lambda message: dp.get('state', {}).get('action') == 'complete_repair')
async def complete_repair_process(message: types.Message):
    """Обработка ввода стоимости и завершение ремонта"""
    try:
        cost = float(message.text.replace(',', '.'))
        repair_id = dp['state']['repair_id']
        
        if db.update_repair_status(repair_id, 'завершён', cost):
            await message.answer(
                f"✅ Ремонт #{repair_id} завершён!\n"
                f"💰 Стоимость: {cost:.2f} руб.",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer("❌ Ошибка при завершении ремонта")
    except ValueError:
        await message.answer("❌ Введите корректную стоимость (число)")
        return
    
    dp['state'] = {}

@dp.message_handler(lambda message: message.text == '✅ Завершённые')
async def show_completed_repairs(message: types.Message):
    """Показать завершённые ремонты"""
    repairs = db.get_all_repairs(status='завершён', limit=20)
    
    if not repairs:
        await message.answer("🔆 Завершённых ремонтов нет.", reply_markup=get_main_keyboard())
        return
    
    text = "✅ *Завершённые ремонты:*\n\n"
    for r in repairs:
        text += (
            f"🆔 #{r['id']}\n"
            f"🚗 {r['car_number']} {r['car_model'] or ''}\n"
            f"📝 {r['description'][:40]}{'...' if len(r['description']) > 40 else ''}\n"
            f"💰 {r['cost']:.2f} руб.\n"
            f"📅 {r['completed_at'].strftime('%d.%m.%Y') if r['completed_at'] else 'Дата неизвестна'}\n"
            f"---\n"
        )
    
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')

@dp.message_handler(lambda message: message.text == '📊 Статистика')
async def show_stats(message: types.Message):
    """Показать статистику"""
    today_stats = db.get_today_stats()
    weekly_stats = db.get_weekly_stats()
    
    text = (
        f"📊 *Статистика ремонтов*\n\n"
        f"*Сегодня:*\n"
        f"📌 Всего: {today_stats['total']}\n"
        f"✅ Завершено: {today_stats['completed']}\n"
        f"💰 Сумма: {today_stats['total_cost']:.2f} руб.\n\n"
        f"*За неделю:*\n"
    )
    
    if weekly_stats:
        for day in weekly_stats[:7]:
            text += (
                f"📅 {day['date'].strftime('%d.%m')}: "
                f"{day['total']} рем., "
                f"{day['completed']} заверш., "
                f"{day['total_cost']:.2f} руб.\n"
            )
    else:
        text += "Нет данных за неделю"
    
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')

@dp.message_handler(lambda message: message.text == '🔍 Поиск по номеру')
async def search_by_car(message: types.Message):
    """Поиск по номеру машины"""
    await message.answer(
        "🔍 Введите номер машины для поиска:\n"
        "(например: А123ВВ77)"
    )
    dp['state'] = {'action': 'search_car', 'user_id': message.from_user.id}

@dp.message_handler(lambda message: dp.get('state', {}).get('action') == 'search_car')
async def search_car_process(message: types.Message):
    """Обработка поиска по номеру"""
    car_number = message.text.strip().upper()
    repairs = db.get_repairs_by_car(car_number)
    
    if not repairs:
        await message.answer(
            f"🚫 Ремонтов для машины {car_number} не найдено.",
            reply_markup=get_main_keyboard()
        )
        dp['state'] = {}
        return
    
    text = f"🔍 *Найдено ремонтов для {car_number}:*\n\n"
    for r in repairs[:10]:
        status_emoji = "✅" if r['status'] == 'завершён' else "🔄"
        text += (
            f"{status_emoji} #{r['id']} | {r['status']}\n"
            f"📝 {r['description'][:50]}{'...' if len(r['description']) > 50 else ''}\n"
            f"{f'💰 {r['cost']:.2f} руб.' if r['cost'] else ''}\n"
            f"---\n"
        )
    
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
    dp['state'] = {}

@dp.message_handler()
async def handle_unknown(message: types.Message):
    """Обработка неизвестных сообщений"""
    await message.answer(
        "🤔 Неизвестная команда. Используйте клавиатуру или /help",
        reply_markup=get_main_keyboard()
    )

# ============= ЗАПУСК =============

if __name__ == '__main__':
    # Проверяем подключение к БД
    if not db.test_connection():
        print("❌ Не удалось подключиться к PostgreSQL. Завершение...")
        exit(1)
    
    # Инициализируем БД
    db.init_db()
    
    # Запускаем бота
    print("🤖 Бот запущен!")
    executor.start_polling(dp, skip_updates=True)
