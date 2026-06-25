import os
import logging
import time
import sys
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
import db
import tempfile
import subprocess
import speech_recognition as sr

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
        types.KeyboardButton('🔍 Поиск по номеру'),
        types.KeyboardButton('✏️ Редактировать ремонт')
    ]
    keyboard.add(*buttons)
    return keyboard

def get_edit_keyboard(repair_id):
    """Клавиатура для выбора поля для редактирования"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🚗 Номер машины", callback_data=f"edit_field_{repair_id}_car_number"),
        InlineKeyboardButton("📝 Описание", callback_data=f"edit_field_{repair_id}_description"),
        InlineKeyboardButton("🚙 Модель", callback_data=f"edit_field_{repair_id}_car_model"),
        InlineKeyboardButton("👨‍🔧 Мастер", callback_data=f"edit_field_{repair_id}_master"),
        InlineKeyboardButton("💰 Стоимость", callback_data=f"edit_field_{repair_id}_cost"),
        InlineKeyboardButton("📊 Статус", callback_data=f"edit_field_{repair_id}_status"),
        InlineKeyboardButton("❌ Отмена", callback_data=f"edit_cancel_{repair_id}")
    )
    return keyboard

def get_status_keyboard(repair_id):
    """Клавиатура для выбора статуса"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔄 В работе", callback_data=f"set_status_{repair_id}_в работе"),
        InlineKeyboardButton("✅ Завершён", callback_data=f"set_status_{repair_id}_завершён"),
        InlineKeyboardButton("⏸ Приостановлен", callback_data=f"set_status_{repair_id}_приостановлен"),
        InlineKeyboardButton("❌ Отмена", callback_data=f"edit_cancel_{repair_id}")
    )
    return keyboard

# ============= ОБРАБОТЧИКИ КОМАНД =============

@dp.message_handler(commands=['start', 'help'])
async def cmd_start(message: types.Message):
    """Обработка команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Проверка в белом списке
    if not db.is_user_whitelisted(user_id):
        if db.add_to_whitelist(user_id, username):
            await message.answer(
                "👋 Привет! Я бот для учёта ремонтов автомобилей.\n\n"
                "Доступные команды:\n"
                "➕ Новый ремонт - добавить новый ремонт\n"
                "📋 Активные ремонты - посмотреть текущие ремонты\n"
                "✅ Завершённые - завершённые ремонты\n"
                "📊 Статистика - статистика по ремонтам\n"
                "🔍 Поиск по номеру - найти все ремонты по госномеру\n"
                "✏️ Редактировать ремонт - изменить данные существующего ремонта\n\n"
                "🎤 Голосовое сообщение в режиме 'Новый ремонт' - автоматическое распознавание",
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
        "🔍 Поиск по номеру - найти все ремонты по госномеру\n"
        "✏️ Редактировать ремонт - изменить данные существующего ремонта\n\n"
        "🎤 Голосовое сообщение в режиме 'Новый ремонт' - автоматическое распознавание",
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
        "Иван Петров\n\n"
        "🎤 Или отправьте голосовое сообщение с описанием!"
    )
    # Устанавливаем состояние
    dp['state'] = {'action': 'add_repair', 'user_id': message.from_user.id}

# ============= ОБРАБОТКА ГОЛОСОВЫХ СООБЩЕНИЙ =============

@dp.message_handler(lambda message: dp.get('state', {}).get('action') == 'add_repair' and message.voice)
async def add_repair_from_voice(message: types.Message):
    """Обработка голосового сообщения для создания нового ремонта"""
    
    # Отправляем сообщение о начале обработки
    processing_msg = await message.answer("🎤 Обрабатываю голосовое сообщение...")
    
    try:
        # Получаем файл голосового сообщения
        voice = message.voice
        file_id = voice.file_id
        file_info = await bot.get_file(file_id)
        
        # Скачиваем файл в память
        voice_bytes = await bot.download_file(file_info.file_path)
        
        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp_ogg:
            tmp_ogg.write(voice_bytes.read())
            tmp_ogg_path = tmp_ogg.name
        
        # Конвертируем OGG в WAV
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_wav:
            tmp_wav_path = tmp_wav.name
        
        try:
            # Конвертация с помощью ffmpeg
            subprocess.run([
                'ffmpeg',
                '-i', tmp_ogg_path,
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                tmp_wav_path,
                '-y'
            ], check=True, capture_output=True)
            
            # Распознаем речь
            recognizer = sr.Recognizer()
            with sr.AudioFile(tmp_wav_path) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data, language='ru-RU')
            
            # Парсим текст голосового сообщения
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            if len(lines) >= 2:
                car_number = lines[0].strip().upper()
                car_model = lines[1].strip() if len(lines) > 1 else None
                description = lines[2].strip() if len(lines) > 2 else "Нет описания"
                master = lines[3].strip() if len(lines) > 3 else None
            else:
                parts = text.replace('.', ',').split(',')
                if len(parts) >= 3:
                    car_number = parts[0].strip().upper()
                    car_model = parts[1].strip() if len(parts) > 1 else None
                    description = parts[2].strip() if len(parts) > 2 else "Нет описания"
                    master = parts[3].strip() if len(parts) > 3 else None
                else:
                    car_number = "НЕ УКАЗАН"
                    car_model = None
                    description = text
                    master = None
            
            # Сохраняем ремонт в базу данных
            repair_id = db.add_repair(
                car_number, 
                description, 
                car_model, 
                master, 
                message.from_user.id
            )
            
            # Сбрасываем состояние
            dp['state'] = {}
            
            # Отправляем подтверждение
            await processing_msg.edit_text(
                f"✅ Ремонт #{repair_id} успешно создан из голосового сообщения!\n\n"
                f"🚗 Номер: {car_number}\n"
                f"📝 Описание: {description}\n"
                f"👨‍🔧 Мастер: {master or 'Не указан'}\n"
                f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"🎤 Распознанный текст:\n{text}",
                reply_markup=get_main_keyboard()
            )
            
        except subprocess.CalledProcessError as e:
            await processing_msg.edit_text(
                "❌ Ошибка при конвертации аудио. Пожалуйста, попробуйте записать сообщение четче или используйте текстовый ввод.",
                reply_markup=get_main_keyboard()
            )
            print(f"FFmpeg error: {e.stderr}")
            
        except sr.UnknownValueError:
            await processing_msg.edit_text(
                "❌ Не удалось распознать речь. Пожалуйста, запишите сообщение четче или используйте текстовый ввод.",
                reply_markup=get_main_keyboard()
            )
            
        except sr.RequestError as e:
            await processing_msg.edit_text(
                "❌ Ошибка сервиса распознавания речи. Попробуйте позже или используйте текстовый ввод.",
                reply_markup=get_main_keyboard()
            )
            print(f"Speech recognition error: {e}")
            
        except Exception as e:
            await processing_msg.edit_text(
                f"❌ Ошибка при обработке: {str(e)}",
                reply_markup=get_main_keyboard()
            )
            print(f"Voice processing error: {e}")
            
        finally:
            try:
                if os.path.exists(tmp_ogg_path):
                    os.unlink(tmp_ogg_path)
                if os.path.exists(tmp_wav_path):
                    os.unlink(tmp_wav_path)
            except Exception as e:
                print(f"Error deleting temp files: {e}")
    
    except Exception as e:
        await processing_msg.edit_text(
            "❌ Произошла ошибка при обработке голосового сообщения. Пожалуйста, попробуйте текстовый ввод.",
            reply_markup=get_main_keyboard()
        )
        print(f"Voice processing error: {e}")
        dp['state'] = {}

# ============= ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ =============

@dp.message_handler(lambda message: dp.get('state', {}).get('action') == 'add_repair' and message.text)
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

# ============= РЕДАКТИРОВАНИЕ РЕМОНТОВ =============

@dp.message_handler(lambda message: message.text == '✏️ Редактировать ремонт')
async def edit_repair_start(message: types.Message):
    """Начало редактирования ремонта"""
    await message.answer(
        "🔍 Введите ID ремонта, который хотите отредактировать.\n"
        "ID можно посмотреть в списке ремонтов.\n\n"
        "Пример: 123"
    )
    dp['state'] = {'action': 'edit_repair_select', 'user_id': message.from_user.id}

@dp.message_handler(lambda message: dp.get('state', {}).get('action') == 'edit_repair_select' and message.text)
async def edit_repair_select(message: types.Message):
    """Выбор ремонта для редактирования"""
    try:
        repair_id = int(message.text.strip())
        repair = db.get_repair(repair_id)
        
        if not repair:
            await message.answer(
                "❌ Ремонт с таким ID не найден. Попробуйте еще раз или /cancel",
                reply_markup=get_main_keyboard()
            )
            dp['state'] = {}
            return
        
        # Показываем информацию о ремонте и предлагаем выбрать поле для редактирования
        text = (
            f"✏️ *Редактирование ремонта #{repair_id}*\n\n"
            f"🚗 Номер: {repair['car_number']}\n"
            f"🚙 Модель: {repair['car_model'] or 'Не указана'}\n"
            f"📝 Описание: {repair['description']}\n"
            f"👨‍🔧 Мастер: {repair['master'] or 'Не указан'}\n"
            f"📊 Статус: {repair['status']}\n"
            f"💰 Стоимость: {repair['cost']:.2f} руб. если завершён\n\n"
            f"Выберите поле для редактирования:"
        )
        
        await message.answer(
            text,
            reply_markup=get_edit_keyboard(repair_id),
            parse_mode='Markdown'
        )
        
        dp['state'] = {'action': 'edit_repair_field', 'repair_id': repair_id, 'user_id': message.from_user.id}
        
    except ValueError:
        await message.answer("❌ Введите корректный ID (число)")
        return

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('edit_field_'))
async def edit_field_callback(callback_query: types.CallbackQuery):
    """Обработка выбора поля для редактирования"""
    await bot.answer_callback_query(callback_query.id)
    
    parts = callback_query.data.split('_')
    repair_id = int(parts[2])
    field = parts[3]
    
    field_names = {
        'car_number': '🚗 Номер машины',
        'car_model': '🚙 Модель',
        'description': '📝 Описание',
        'master': '👨‍🔧 Мастер',
        'cost': '💰 Стоимость',
        'status': '📊 Статус'
    }
    
    if field == 'status':
        # Показываем клавиатуру для выбора статуса
        await bot.send_message(
            callback_query.from_user.id,
            f"Выберите новый статус для ремонта #{repair_id}:",
            reply_markup=get_status_keyboard(repair_id)
        )
        return
    
    # Для остальных полей запрашиваем ввод
    await bot.send_message(
        callback_query.from_user.id,
        f"Введите новое значение для поля '{field_names.get(field, field)}':\n\n"
        f"Текущее значение: {get_current_field_value(repair_id, field)}\n\n"
        f"Для отмены введите /cancel"
    )
    
    dp['state'] = {
        'action': 'edit_repair_input',
        'repair_id': repair_id,
        'field': field,
        'user_id': callback_query.from_user.id
    }

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('set_status_'))
async def set_status_callback(callback_query: types.CallbackQuery):
    """Обработка установки статуса"""
    await bot.answer_callback_query(callback_query.id)
    
    parts = callback_query.data.split('_')
    repair_id = int(parts[2])
    status = parts[3]
    
    try:
        # Если статус "завершён", запрашиваем стоимость
        if status == 'завершён':
            await bot.send_message(
                callback_query.from_user.id,
                f"💰 Введите стоимость для ремонта #{repair_id}:"
            )
            dp['state'] = {
                'action': 'edit_repair_cost_for_status',
                'repair_id': repair_id,
                'status': status,
                'user_id': callback_query.from_user.id
            }
            return
        
        # Обновляем статус
        if db.update_repair_status(repair_id, status):
            await bot.send_message(
                callback_query.from_user.id,
                f"✅ Статус ремонта #{repair_id} обновлен на '{status}'",
                reply_markup=get_main_keyboard()
            )
        else:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Ошибка при обновлении статуса",
                reply_markup=get_main_keyboard()
            )
            
    except Exception as e:
        await bot.send_message(
            callback_query.from_user.id,
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_keyboard()
        )
    
    dp['state'] = {}

@dp.message_handler(lambda message: dp.get('state', {}).get('action') == 'edit_repair_cost_for_status' and message.text)
async def edit_repair_cost_for_status(message: types.Message):
    """Ввод стоимости при завершении ремонта"""
    try:
        cost = float(message.text.replace(',', '.'))
        repair_id = dp['state']['repair_id']
        status = dp['state']['status']
        
        if db.update_repair_status(repair_id, status, cost):
            await message.answer(
                f"✅ Ремонт #{repair_id} завершён!\n"
                f"💰 Стоимость: {cost:.2f} руб.",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer("❌ Ошибка при обновлении статуса")
            
    except ValueError:
        await message.answer("❌ Введите корректную стоимость (число)")
        return
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    dp['state'] = {}

@dp.message_handler(lambda message: dp.get('state', {}).get('action') == 'edit_repair_input' and message.text)
async def edit_repair_input(message: types.Message):
    """Обработка ввода нового значения для поля"""
    if message.text.lower() == '/cancel':
        await message.answer("❌ Редактирование отменено.", reply_markup=get_main_keyboard())
        dp['state'] = {}
        return
    
    repair_id = dp['state']['repair_id']
    field = dp['state']['field']
    new_value = message.text.strip()
    
    try:
        # Преобразуем значение для соответствующих полей
        if field == 'cost':
            new_value = float(new_value.replace(',', '.'))
        
        # Обновляем поле в БД
        if db.update_repair_field(repair_id, field, new_value):
            repair = db.get_repair(repair_id)
            
            await message.answer(
                f"✅ Поле успешно обновлено!\n\n"
                f"✏️ *Обновленный ремонт #{repair_id}*\n"
                f"🚗 Номер: {repair['car_number']}\n"
                f"🚙 Модель: {repair['car_model'] or 'Не указана'}\n"
                f"📝 Описание: {repair['description']}\n"
                f"👨‍🔧 Мастер: {repair['master'] or 'Не указан'}\n"
                f"📊 Статус: {repair['status']}\n"
                f"💰 Стоимость: {repair['cost']:.2f} руб. если завершён",
                reply_markup=get_main_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await message.answer("❌ Ошибка при обновлении поля")
            
    except ValueError:
        await message.answer("❌ Введите корректное значение для поля")
        return
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    
    dp['state'] = {}

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('edit_cancel_'))
async def edit_cancel_callback(callback_query: types.CallbackQuery):
    """Отмена редактирования"""
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "❌ Редактирование отменено.",
        reply_markup=get_main_keyboard()
    )
    dp['state'] = {}

def get_current_field_value(repair_id, field):
    """Получить текущее значение поля"""
    repair = db.get_repair(repair_id)
    if not repair:
        return "Не найдено"
    
    value = repair.get(field)
    if value is None:
        return "Не указано"
    if field == 'cost' and value:
        return f"{value:.2f} руб."
    return str(value)

# ============= ОСТАЛЬНЫЕ ОБРАБОТЧИКИ =============

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
    for r in repairs[:5]:
        keyboard.add(
            InlineKeyboardButton(f"✅ Завершить #{r['id']}", callback_data=f"complete_{r['id']}"),
            InlineKeyboardButton(f"✏️ Редактировать #{r['id']}", callback_data=f"edit_from_list_{r['id']}")
        )
    
    await message.answer(text, reply_markup=keyboard, parse_mode='Markdown')

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('edit_from_list_'))
async def edit_from_list_callback(callback_query: types.CallbackQuery):
    """Быстрое редактирование из списка"""
    await bot.answer_callback_query(callback_query.id)
    
    repair_id = int(callback_query.data.split('_')[3])
    repair = db.get_repair(repair_id)
    
    if not repair:
        await bot.send_message(callback_query.from_user.id, "❌ Ремонт не найден")
        return
    
    text = (
        f"✏️ *Редактирование ремонта #{repair_id}*\n\n"
        f"🚗 Номер: {repair['car_number']}\n"
        f"🚙 Модель: {repair['car_model'] or 'Не указана'}\n"
        f"📝 Описание: {repair['description']}\n"
        f"👨‍🔧 Мастер: {repair['master'] or 'Не указан'}\n"
        f"📊 Статус: {repair['status']}\n"
        f"💰 Стоимость: {repair['cost']:.2f} руб. если завершён\n\n"
        f"Выберите поле для редактирования:"
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        text,
        reply_markup=get_edit_keyboard(repair_id),
        parse_mode='Markdown'
    )
    
    dp['state'] = {'action': 'edit_repair_field', 'repair_id': repair_id, 'user_id': callback_query.from_user.id}

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
    await bot.send_message(
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
        cost_str = f"💰 {r['cost']:.2f} руб." if r['cost'] else ""
        
        text += (
            f"{status_emoji} #{r['id']} | {r['status']}\n"
            f"📝 {r['description'][:50]}{'...' if len(r['description']) > 50 else ''}\n"
            f"{cost_str}\n"
            f"---\n"
        )
    
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
    dp['state'] = {}

@dp.message_handler(commands=['cancel'])
async def cmd_cancel(message: types.Message):
    """Отмена текущего действия"""
    if dp.get('state'):
        dp['state'] = {}
        await message.answer("❌ Действие отменено.", reply_markup=get_main_keyboard())
    else:
        await message.answer("Нет активных действий для отмены.", reply_markup=get_main_keyboard())

@dp.message_handler()
async def handle_unknown(message: types.Message):
    """Обработка неизвестных сообщений"""
    await message.answer(
        "🤔 Неизвестная команда. Используйте клавиатуру или /help",
        reply_markup=get_main_keyboard()
    )

# ============= ЗАПУСК =============

async def on_startup(dp):
    """Действия при запуске бота"""
    try:
        await bot.delete_webhook()
        print("✅ Webhook удалён")
        
        # Устанавливаем команды бота
        await bot.set_my_commands([
            BotCommand("start", "Начать работу"),
            BotCommand("help", "Помощь"),
            BotCommand("cancel", "Отменить действие")
        ])
        print("✅ Команды установлены")
        
        print("🤖 Бот запущен и готов к работе!")
    except Exception as e:
        print(f"⚠️ Ошибка при старте: {e}")

if __name__ == '__main__':
    try:
        print("🚀 Запуск repairBot...")
        print(f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Проверяем переменные окружения
        token = os.getenv('BOT_TOKEN')
        db_url = os.getenv('DATABASE_URL')
        
        if not token:
            print("❌ ОШИБКА: BOT_TOKEN не установлен!")
            exit(1)
        
        if not db_url:
            print("❌ ОШИБКА: DATABASE_URL не установлен!")
            exit(1)
        
        print("✅ Переменные окружения проверены")
        
        # Проверяем подключение к БД
        print("⏳ Проверка подключения к БД...")
        if not db.test_connection():
            print("❌ Не удалось подключиться к PostgreSQL. Завершение...")
            exit(1)
        print("✅ Подключение к БД успешно")
        
        # Инициализируем БД
        print("⏳ Инициализация БД...")
        db.init_db()
        print("✅ Б