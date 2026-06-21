import os
import re
import sqlite3
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import speech_recognition as sr
from pydub import AudioSegment

# ---------- Настройки ----------
# ВСТАВЬТЕ СЮДА ВАШ НОВЫЙ ТОКЕН ОТ @BotFather
TOKEN = "8818860457:AAF2bEUKZZ_DlOlWIO7byjpYNblTOpeo3j0"
DB_NAME = "repairs.db"

logging.basicConfig(level=logging.INFO)

# ---------- База данных ----------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS repairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    car_number TEXT,
                    what_done TEXT,
                    who_did TEXT,
                    cost REAL DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                 )''')
    conn.commit()
    conn.close()

def save_repair(car_number, what_done, who_did, cost):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO repairs (car_number, what_done, who_did, cost) VALUES (?, ?, ?, ?)",
              (car_number, what_done, who_did, cost))
    conn.commit()
    conn.close()

def get_repairs(car_number=None, days=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    query = "SELECT * FROM repairs WHERE timestamp >= ?"
    params = []
    if days is not None:
        since = datetime.now() - timedelta(days=days)
    else:
        since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    params.append(since.isoformat())

    if car_number:
        query += " AND car_number = ?"
        params.append(car_number)

    query += " ORDER BY timestamp DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

# ---------- Распознавание голоса ----------
def voice_to_text(voice_file_path):
    audio = AudioSegment.from_ogg(voice_file_path)
    wav_path = voice_file_path.replace(".ogg", ".wav")
    audio.export(wav_path, format="wav")

    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio_data, language="ru-RU")
    except sr.UnknownValueError:
        text = ""
    except sr.RequestError:
        text = ""

    os.remove(voice_file_path)
    os.remove(wav_path)
    return text

# ---------- Парсинг текста ----------
def parse_repair_text(text):
    text = text.lower().strip()
    # Извлекаем номер машины
    car_match = re.search(r'(?:машин[аы]?\s*)?(\d+)', text)
    car_number = car_match.group(1) if car_match else "неизвестно"

    # Удаляем номер машины из текста для дальнейшего поиска
    rest = text
    if car_match:
        rest = rest.replace(car_match.group(0), "")

    # Ищем исполнителя
    who_match = re.search(r'(?:слесарь|мастер|делал\s*)?\s*([а-яё]+(?:[-\s][а-яё]+)?)', rest)
    who_did = who_match.group(1).strip() if who_match else "неизвестно"

    # Удаляем исполнителя из остатка
    if who_match:
        rest = rest.replace(who_match.group(1), "")

    # Ищем сумму (число, возможно с десятичной частью)
    cost_match = re.search(r'(\d+[.,]?\d*)', rest)
    cost = float(cost_match.group(1).replace(',', '.')) if cost_match else 0.0

    # Удаляем сумму из остатка
    if cost_match:
        rest = rest.replace(cost_match.group(0), "")

    # Очищаем описание от лишних знаков
    what_done = re.sub(r'[,.;:!?]+', ' ', rest).strip()
    if not what_done:
        what_done = "не указано"

    return car_number, what_done, who_did, cost

# ---------- Обработчики команд ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Бот для учёта ремонта машин.\n"
        "Пришли голосовое или текст в формате:\n"
        "Машина 5, замена масла, 2500, слесарь Петров\n"
        "Команды:\n"
        "/history - последние записи (все)\n"
        "/history 5 - по машине №5\n"
"/report - отчёт за сегодня\n"
        "/report 5 - за сегодня по машине 5\n"
        "/report 7 - за 7 дней по всем\n"
        "/report 5 7 - за 7 дней по машине 5"
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    if not voice:
        return
    file = await context.bot.get_file(voice.file_id)
    ogg_path = f"voice_{voice.file_unique_id}.ogg"
    await file.download_to_drive(ogg_path)

    await update.message.reply_text("🔄 Распознаю голос...")
    text = voice_to_text(ogg_path)
    if not text:
        await update.message.reply_text("❌ Не распознано. Попробуйте чётче.")
        return

    car_number, what_done, who_did, cost = parse_repair_text(text)
    save_repair(car_number, what_done, who_did, cost)

    reply = (f"✅ Записано!\n"
             f"Машина: {car_number}\n"
             f"Работа: {what_done}\n"
             f"Сумма: {cost} руб.\n"
             f"Кто: {who_did}\n"
             f"Распознанный текст: {text}")
    await update.message.reply_text(reply)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith('/'):
        return
    car_number, what_done, who_did, cost = parse_repair_text(text)
    save_repair(car_number, what_done, who_did, cost)
    await update.message.reply_text(
        f"✅ Записано из текста:\n"
        f"Машина {car_number}\n"
        f"Работа: {what_done}\n"
        f"Сумма: {cost} руб.\n"
        f"Кто: {who_did}"
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    car_filter = args[0] if args else None
    rows = get_repairs(car_number=car_filter, days=30)
    if not rows:
        await update.message.reply_text("Записей нет.")
        return
    msg = "📋 Последние записи (за 30 дней):\n"
    total = 0
    for row in rows[:10]:
        msg += f"#{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} руб. | {row[5][:16]}\n"
        total += row[4]
    msg += f"\nОбщая сумма по показанным: {total} руб."
    await update.message.reply_text(msg)

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    car_filter = None
    days = None

    if len(args) == 0:
        days = 0
    elif len(args) == 1:
        if args[0].isdigit():
            days = int(args[0])
        else:
            car_filter = args[0]
            days = 0
    elif len(args) >= 2:
        car_filter = args[0]
        days = int(args[1])

    rows = get_repairs(car_number=car_filter, days=days)
    if not rows:
        await update.message.reply_text("Записей за выбранный период нет.")
        return

    msg = f"📊 Отчёт{' по машине ' + car_filter if car_filter else ''} за "
    if days == 0:
        msg += "сегодня"
    elif days == 1:
        msg += "последний день"
    else:
        msg += f"последние {days} дней"
    msg += ":\n\n"

    total = 0
    for row in rows:
        msg += f"{row[5][:16]} | Маш.{row[1]} | {row[2]} | {row[3]} | {row[4]} руб.\n"
        total += row[4]
    msg += f"\n💰 Итого: {total} руб."

    if len(msg) > 4096:
        msg = msg[:4000] + "\n... (обрезано)"

    await update.message.reply_text(msg)

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if name == "__main__":
    main()
