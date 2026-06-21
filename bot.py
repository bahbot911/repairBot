{\rtf1\ansi\ansicpg1251\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;\f1\fnil\fcharset0 AppleColorEmoji;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx566\tx1133\tx1700\tx2267\tx2834\tx3401\tx3968\tx4535\tx5102\tx5669\tx6236\tx6803\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import os\
import re\
import sqlite3\
import logging\
from datetime import datetime, timedelta\
\
from telegram import Update, Voice\
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes\
\
import speech_recognition as sr\
from pydub import AudioSegment\
\
# ---------- \uc0\u1053 \u1072 \u1089 \u1090 \u1088 \u1086 \u1081 \u1082 \u1080  ----------\
TOKEN = "8818860457:AAF2bEUKZZ_DlOlWIO7byjpYNblTOpeo3j0"   # \uc0\u1042 \u1072 \u1096  \u1090 \u1086 \u1082 \u1077 \u1085  (\u1079 \u1072 \u1084 \u1077 \u1085 \u1080 \u1090 \u1077  \u1085 \u1072  \u1085 \u1086 \u1074 \u1099 \u1081  \u1087 \u1088 \u1080  \u1085 \u1077 \u1086 \u1073 \u1093 \u1086 \u1076 \u1080 \u1084 \u1086 \u1089 \u1090 \u1080 )\
DB_NAME = "repairs.db"\
\
logging.basicConfig(level=logging.INFO)\
\
# ---------- \uc0\u1041 \u1072 \u1079 \u1072  \u1076 \u1072 \u1085 \u1085 \u1099 \u1093  ----------\
def init_db():\
    conn = sqlite3.connect(DB_NAME)\
    c = conn.cursor()\
    c.execute('''CREATE TABLE IF NOT EXISTS repairs (\
                    id INTEGER PRIMARY KEY AUTOINCREMENT,\
                    car_number TEXT,\
                    what_done TEXT,\
                    who_did TEXT,\
                    cost REAL DEFAULT 0,\
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP\
                 )''')\
    conn.commit()\
    conn.close()\
\
def save_repair(car_number, what_done, who_did, cost):\
    conn = sqlite3.connect(DB_NAME)\
    c = conn.cursor()\
    c.execute("INSERT INTO repairs (car_number, what_done, who_did, cost) VALUES (?, ?, ?, ?)",\
              (car_number, what_done, who_did, cost))\
    conn.commit()\
    conn.close()\
\
def get_repairs(car_number=None, days=None):\
    """\
    \uc0\u1042 \u1086 \u1079 \u1074 \u1088 \u1072 \u1097 \u1072 \u1077 \u1090  \u1079 \u1072 \u1087 \u1080 \u1089 \u1080  \u1079 \u1072  \u1087 \u1086 \u1089 \u1083 \u1077 \u1076 \u1085 \u1080 \u1077  days \u1076 \u1085 \u1077 \u1081  (\u1077 \u1089 \u1083 \u1080  None - \u1079 \u1072  \u1089 \u1077 \u1075 \u1086 \u1076 \u1085 \u1103 )\
    \uc0\u1080  \u1086 \u1087 \u1094 \u1080 \u1086 \u1085 \u1072 \u1083 \u1100 \u1085 \u1086  \u1092 \u1080 \u1083 \u1100 \u1090 \u1088 \u1091 \u1077 \u1090  \u1087 \u1086  car_number.\
    """\
    conn = sqlite3.connect(DB_NAME)\
    c = conn.cursor()\
    query = "SELECT * FROM repairs WHERE timestamp >= ?"\
    params = []\
    if days is not None:\
        since = datetime.now() - timedelta(days=days)\
    else:\
        since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)  # \uc0\u1089 \u1077 \u1075 \u1086 \u1076 \u1085 \u1103  \u1089  00:00\
    params.append(since.isoformat())\
\
    if car_number:\
        query += " AND car_number = ?"\
        params.append(car_number)\
\
    query += " ORDER BY timestamp DESC"\
    c.execute(query, params)\
    rows = c.fetchall()\
    conn.close()\
    return rows\
\
# ---------- \uc0\u1056 \u1072 \u1089 \u1087 \u1086 \u1079 \u1085 \u1072 \u1074 \u1072 \u1085 \u1080 \u1077  \u1075 \u1086 \u1083 \u1086 \u1089 \u1072  ----------\
def voice_to_text(voice_file_path):\
    audio = AudioSegment.from_ogg(voice_file_path)\
    wav_path = voice_file_path.replace(".ogg", ".wav")\
    audio.export(wav_path, format="wav")\
\
    recognizer = sr.Recognizer()\
    with sr.AudioFile(wav_path) as source:\
        audio_data = recognizer.record(source)\
    try:\
        text = recognizer.recognize_google(audio_data, language="ru-RU")\
    except sr.UnknownValueError:\
        text = ""\
    except sr.RequestError:\
        text = ""\
\
    os.remove(voice_file_path)\
    os.remove(wav_path)\
    return text\
\
# ---------- \uc0\u1055 \u1072 \u1088 \u1089 \u1080 \u1085 \u1075  \u1090 \u1077 \u1082 \u1089 \u1090 \u1072  ----------\
def parse_repair_text(text):\
    text = text.lower().strip()\
    # \uc0\u1048 \u1079 \u1074 \u1083 \u1077 \u1082 \u1072 \u1077 \u1084  \u1085 \u1086 \u1084 \u1077 \u1088  \u1084 \u1072 \u1096 \u1080 \u1085 \u1099 \
    car_match = re.search(r'(?:\uc0\u1084 \u1072 \u1096 \u1080 \u1085 [\u1072 \u1099 ]?\\s*)?(\\d+)', text)\
    car_number = car_match.group(1) if car_match else "\uc0\u1085 \u1077 \u1080 \u1079 \u1074 \u1077 \u1089 \u1090 \u1085 \u1086 "\
\
    # \uc0\u1059 \u1076 \u1072 \u1083 \u1103 \u1077 \u1084  \u1085 \u1086 \u1084 \u1077 \u1088  \u1084 \u1072 \u1096 \u1080 \u1085 \u1099  \u1080 \u1079  \u1090 \u1077 \u1082 \u1089 \u1090 \u1072  \u1076 \u1083 \u1103  \u1076 \u1072 \u1083 \u1100 \u1085 \u1077 \u1081 \u1096 \u1077 \u1075 \u1086  \u1087 \u1086 \u1080 \u1089 \u1082 \u1072 \
    rest = text\
    if car_match:\
        rest = rest.replace(car_match.group(0), "")\
\
    # \uc0\u1048 \u1097 \u1077 \u1084  \u1080 \u1089 \u1087 \u1086 \u1083 \u1085 \u1080 \u1090 \u1077 \u1083 \u1103 \
    who_match = re.search(r'(?:\uc0\u1089 \u1083 \u1077 \u1089 \u1072 \u1088 \u1100 |\u1084 \u1072 \u1089 \u1090 \u1077 \u1088 |\u1076 \u1077 \u1083 \u1072 \u1083 \\s*)?\\s*([\u1072 -\u1103 \u1105 ]+(?:[-\\s][\u1072 -\u1103 \u1105 ]+)?)', rest)\
    who_did = who_match.group(1).strip() if who_match else "\uc0\u1085 \u1077 \u1080 \u1079 \u1074 \u1077 \u1089 \u1090 \u1085 \u1086 "\
\
    # \uc0\u1059 \u1076 \u1072 \u1083 \u1103 \u1077 \u1084  \u1080 \u1089 \u1087 \u1086 \u1083 \u1085 \u1080 \u1090 \u1077 \u1083 \u1103  \u1080 \u1079  \u1086 \u1089 \u1090 \u1072 \u1090 \u1082 \u1072 \
    if who_match:\
        rest = rest.replace(who_match.group(1), "")\
\
    # \uc0\u1048 \u1097 \u1077 \u1084  \u1089 \u1091 \u1084 \u1084 \u1091  (\u1095 \u1080 \u1089 \u1083 \u1086 , \u1074 \u1086 \u1079 \u1084 \u1086 \u1078 \u1085 \u1086  \u1089  \u1076 \u1077 \u1089 \u1103 \u1090 \u1080 \u1095 \u1085 \u1086 \u1081  \u1095 \u1072 \u1089 \u1090 \u1100 \u1102 )\
    cost_match = re.search(r'(\\d+[.,]?\\d*)', rest)\
    cost = float(cost_match.group(1).replace(',', '.')) if cost_match else 0.0\
\
    # \uc0\u1059 \u1076 \u1072 \u1083 \u1103 \u1077 \u1084  \u1089 \u1091 \u1084 \u1084 \u1091  \u1080 \u1079  \u1086 \u1089 \u1090 \u1072 \u1090 \u1082 \u1072 \
    if cost_match:\
        rest = rest.replace(cost_match.group(0), "")\
\
    # \uc0\u1054 \u1095 \u1080 \u1097 \u1072 \u1077 \u1084  \u1086 \u1087 \u1080 \u1089 \u1072 \u1085 \u1080 \u1077  \u1086 \u1090  \u1083 \u1080 \u1096 \u1085 \u1080 \u1093  \u1079 \u1085 \u1072 \u1082 \u1086 \u1074 \
    what_done = re.sub(r'[,.;:!?]+', ' ', rest).strip()\
    if not what_done:\
        what_done = "\uc0\u1085 \u1077  \u1091 \u1082 \u1072 \u1079 \u1072 \u1085 \u1086 "\
\
    return car_number, what_done, who_did, cost\
\
# ---------- \uc0\u1054 \u1073 \u1088 \u1072 \u1073 \u1086 \u1090 \u1095 \u1080 \u1082 \u1080  \u1082 \u1086 \u1084 \u1072 \u1085 \u1076  ----------\
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):\
    await update.message.reply_text(\
        "\uc0\u1055 \u1088 \u1080 \u1074 \u1077 \u1090 ! \u1041 \u1086 \u1090  \u1076 \u1083 \u1103  \u1091 \u1095 \u1105 \u1090 \u1072  \u1088 \u1077 \u1084 \u1086 \u1085 \u1090 \u1072  \u1084 \u1072 \u1096 \u1080 \u1085 .\\n"\
"\uc0\u1055 \u1088 \u1080 \u1096 \u1083 \u1080  \u1075 \u1086 \u1083 \u1086 \u1089 \u1086 \u1074 \u1086 \u1077  \u1080 \u1083 \u1080  \u1090 \u1077 \u1082 \u1089 \u1090  \u1074  \u1092 \u1086 \u1088 \u1084 \u1072 \u1090 \u1077 :\\n"\
        "\uc0\u1052 \u1072 \u1096 \u1080 \u1085 \u1072  5, \u1079 \u1072 \u1084 \u1077 \u1085 \u1072  \u1084 \u1072 \u1089 \u1083 \u1072 , 2500, \u1089 \u1083 \u1077 \u1089 \u1072 \u1088 \u1100  \u1055 \u1077 \u1090 \u1088 \u1086 \u1074 \\n"\
        "\uc0\u1050 \u1086 \u1084 \u1072 \u1085 \u1076 \u1099 :\\n"\
        "/history - \uc0\u1087 \u1086 \u1089 \u1083 \u1077 \u1076 \u1085 \u1080 \u1077  \u1079 \u1072 \u1087 \u1080 \u1089 \u1080  (\u1074 \u1089 \u1077 )\\n"\
        "/history 5 - \uc0\u1087 \u1086  \u1084 \u1072 \u1096 \u1080 \u1085 \u1077  \u8470 5\\n"\
        "/report - \uc0\u1086 \u1090 \u1095 \u1105 \u1090  \u1079 \u1072  \u1089 \u1077 \u1075 \u1086 \u1076 \u1085 \u1103 \\n"\
        "/report 5 - \uc0\u1079 \u1072  \u1089 \u1077 \u1075 \u1086 \u1076 \u1085 \u1103  \u1087 \u1086  \u1084 \u1072 \u1096 \u1080 \u1085 \u1077  5\\n"\
        "/report 7 - \uc0\u1079 \u1072  7 \u1076 \u1085 \u1077 \u1081  \u1087 \u1086  \u1074 \u1089 \u1077 \u1084 \\n"\
        "/report 5 7 - \uc0\u1079 \u1072  7 \u1076 \u1085 \u1077 \u1081  \u1087 \u1086  \u1084 \u1072 \u1096 \u1080 \u1085 \u1077  5"\
    )\
\
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):\
    voice = update.message.voice\
    if not voice:\
        return\
    file = await context.bot.get_file(voice.file_id)\
    ogg_path = f"voice_\{voice.file_unique_id\}.ogg"\
    await file.download_to_drive(ogg_path)\
\
    await update.message.reply_text("
\f1 \uc0\u55357 \u56580 
\f0  \uc0\u1056 \u1072 \u1089 \u1087 \u1086 \u1079 \u1085 \u1072 \u1102  \u1075 \u1086 \u1083 \u1086 \u1089 ...")\
    text = voice_to_text(ogg_path)\
    if not text:\
        await update.message.reply_text("
\f1 \uc0\u10060 
\f0  \uc0\u1053 \u1077  \u1088 \u1072 \u1089 \u1087 \u1086 \u1079 \u1085 \u1072 \u1085 \u1086 . \u1055 \u1086 \u1087 \u1088 \u1086 \u1073 \u1091 \u1081 \u1090 \u1077  \u1095 \u1105 \u1090 \u1095 \u1077 .")\
        return\
\
    car_number, what_done, who_did, cost = parse_repair_text(text)\
    save_repair(car_number, what_done, who_did, cost)\
\
    reply = (f"
\f1 \uc0\u9989 
\f0  \uc0\u1047 \u1072 \u1087 \u1080 \u1089 \u1072 \u1085 \u1086 !\\n"\
             f"\uc0\u1052 \u1072 \u1096 \u1080 \u1085 \u1072 : \{car_number\}\\n"\
             f"\uc0\u1056 \u1072 \u1073 \u1086 \u1090 \u1072 : \{what_done\}\\n"\
             f"\uc0\u1057 \u1091 \u1084 \u1084 \u1072 : \{cost\} \u1088 \u1091 \u1073 .\\n"\
             f"\uc0\u1050 \u1090 \u1086 : \{who_did\}\\n"\
             f"\uc0\u1056 \u1072 \u1089 \u1087 \u1086 \u1079 \u1085 \u1072 \u1085 \u1085 \u1099 \u1081  \u1090 \u1077 \u1082 \u1089 \u1090 : \{text\}")\
    await update.message.reply_text(reply)\
\
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):\
    text = update.message.text\
    if text.startswith('/'):\
        return\
    car_number, what_done, who_did, cost = parse_repair_text(text)\
    save_repair(car_number, what_done, who_did, cost)\
    await update.message.reply_text(\
        f"
\f1 \uc0\u9989 
\f0  \uc0\u1047 \u1072 \u1087 \u1080 \u1089 \u1072 \u1085 \u1086  \u1080 \u1079  \u1090 \u1077 \u1082 \u1089 \u1090 \u1072 :\\n"\
        f"\uc0\u1052 \u1072 \u1096 \u1080 \u1085 \u1072  \{car_number\}\\n"\
        f"\uc0\u1056 \u1072 \u1073 \u1086 \u1090 \u1072 : \{what_done\}\\n"\
        f"\uc0\u1057 \u1091 \u1084 \u1084 \u1072 : \{cost\} \u1088 \u1091 \u1073 .\\n"\
        f"\uc0\u1050 \u1090 \u1086 : \{who_did\}"\
    )\
\
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):\
    args = context.args\
    car_filter = args[0] if args else None\
    rows = get_repairs(car_number=car_filter, days=30)  # \uc0\u1079 \u1072  \u1087 \u1086 \u1089 \u1083 \u1077 \u1076 \u1085 \u1080 \u1077  30 \u1076 \u1085 \u1077 \u1081 \
    if not rows:\
        await update.message.reply_text("\uc0\u1047 \u1072 \u1087 \u1080 \u1089 \u1077 \u1081  \u1085 \u1077 \u1090 .")\
        return\
    msg = "
\f1 \uc0\u55357 \u56523 
\f0  \uc0\u1055 \u1086 \u1089 \u1083 \u1077 \u1076 \u1085 \u1080 \u1077  \u1079 \u1072 \u1087 \u1080 \u1089 \u1080  (\u1079 \u1072  30 \u1076 \u1085 \u1077 \u1081 ):\\n"\
    total = 0\
    for row in rows[:10]:\
        msg += f"#\{row[0]\} | \{row[1]\} | \{row[2]\} | \{row[3]\} | \{row[4]\} \uc0\u1088 \u1091 \u1073 . | \{row[5][:16]\}\\n"\
        total += row[4]\
    msg += f"\\n\uc0\u1054 \u1073 \u1097 \u1072 \u1103  \u1089 \u1091 \u1084 \u1084 \u1072  \u1087 \u1086  \u1087 \u1086 \u1082 \u1072 \u1079 \u1072 \u1085 \u1085 \u1099 \u1084 : \{total\} \u1088 \u1091 \u1073 ."\
    await update.message.reply_text(msg)\
\
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):\
    args = context.args\
    car_filter = None\
    days = None\
\
    if len(args) == 0:\
        # \uc0\u1086 \u1090 \u1095 \u1105 \u1090  \u1079 \u1072  \u1089 \u1077 \u1075 \u1086 \u1076 \u1085 \u1103 \
        days = 0  # \uc0\u1073 \u1091 \u1076 \u1077 \u1090  \u1080 \u1085 \u1090 \u1077 \u1088 \u1087 \u1088 \u1077 \u1090 \u1080 \u1088 \u1086 \u1074 \u1072 \u1085 \u1086  \u1082 \u1072 \u1082  \u1089 \u1077 \u1075 \u1086 \u1076 \u1085 \u1103 \
    elif len(args) == 1:\
        # \uc0\u1084 \u1086 \u1078 \u1077 \u1090  \u1073 \u1099 \u1090 \u1100  \u1085 \u1086 \u1084 \u1077 \u1088  \u1084 \u1072 \u1096 \u1080 \u1085 \u1099  \u1080 \u1083 \u1080  \u1082 \u1086 \u1083 \u1080 \u1095 \u1077 \u1089 \u1090 \u1074 \u1086  \u1076 \u1085 \u1077 \u1081 \
        if args[0].isdigit():\
            # \uc0\u1077 \u1089 \u1083 \u1080  \u1072 \u1088 \u1075 \u1091 \u1084 \u1077 \u1085 \u1090  \u1095 \u1080 \u1089 \u1083 \u1086 , \u1089 \u1095 \u1080 \u1090 \u1072 \u1077 \u1084  \u1095 \u1090 \u1086  \u1101 \u1090 \u1086  \u1076 \u1085 \u1080  (\u1077 \u1089 \u1083 \u1080  \u1087 \u1086 \u1083 \u1100 \u1079 \u1086 \u1074 \u1072 \u1090 \u1077 \u1083 \u1100  \u1093 \u1086 \u1095 \u1077 \u1090  \u1084 \u1072 \u1096 \u1080 \u1085 \u1091 , \u1086 \u1085  \u1076 \u1086 \u1083 \u1078 \u1077 \u1085  \u1091 \u1082 \u1072 \u1079 \u1072 \u1090 \u1100  2 \u1072 \u1088 \u1075 \u1091 \u1084 \u1077 \u1085 \u1090 \u1072 )\
            days = int(args[0])\
        else:\
            car_filter = args[0]\
            days = 0\
    elif len(args) >= 2:\
        car_filter = args[0]\
        days = int(args[1])\
\
    rows = get_repairs(car_number=car_filter, days=days)\
    if not rows:\
        await update.message.reply_text("\uc0\u1047 \u1072 \u1087 \u1080 \u1089 \u1077 \u1081  \u1079 \u1072  \u1074 \u1099 \u1073 \u1088 \u1072 \u1085 \u1085 \u1099 \u1081  \u1087 \u1077 \u1088 \u1080 \u1086 \u1076  \u1085 \u1077 \u1090 .")\
        return\
\
    msg = f"
\f1 \uc0\u55357 \u56522 
\f0  \uc0\u1054 \u1090 \u1095 \u1105 \u1090 \{' \u1087 \u1086  \u1084 \u1072 \u1096 \u1080 \u1085 \u1077  ' + car_filter if car_filter else ''\} \u1079 \u1072  "\
    if days == 0:\
        msg += "\uc0\u1089 \u1077 \u1075 \u1086 \u1076 \u1085 \u1103 "\
    elif days == 1:\
        msg += "\uc0\u1087 \u1086 \u1089 \u1083 \u1077 \u1076 \u1085 \u1080 \u1081  \u1076 \u1077 \u1085 \u1100 "\
    else:\
        msg += f"\uc0\u1087 \u1086 \u1089 \u1083 \u1077 \u1076 \u1085 \u1080 \u1077  \{days\} \u1076 \u1085 \u1077 \u1081 "\
    msg += ":\\n\\n"\
\
    total = 0\
    for row in rows:\
        msg += f"\{row[5][:16]\} | \uc0\u1052 \u1072 \u1096 .\{row[1]\} | \{row[2]\} | \{row[3]\} | \{row[4]\} \u1088 \u1091 \u1073 .\\n"\
        total += row[4]\
    msg += f"\\n
\f1 \uc0\u55357 \u56496 
\f0  \uc0\u1048 \u1090 \u1086 \u1075 \u1086 : \{total\} \u1088 \u1091 \u1073 ."\
\
    if len(msg) > 4096:\
        # \uc0\u1077 \u1089 \u1083 \u1080  \u1089 \u1083 \u1080 \u1096 \u1082 \u1086 \u1084  \u1076 \u1083 \u1080 \u1085 \u1085 \u1086 \u1077 , \u1086 \u1073 \u1088 \u1077 \u1079 \u1072 \u1077 \u1084  \u1080 \u1083 \u1080  \u1088 \u1072 \u1079 \u1073 \u1080 \u1074 \u1072 \u1077 \u1084  (\u1076 \u1083 \u1103  \u1087 \u1088 \u1086 \u1089 \u1090 \u1086 \u1090 \u1099  \u1086 \u1073 \u1088 \u1077 \u1078 \u1077 \u1084  \u1076 \u1086  4000)\
        msg = msg[:4000] + "\\n... (\uc0\u1086 \u1073 \u1088 \u1077 \u1079 \u1072 \u1085 \u1086 )"\
\
    await update.message.reply_text(msg)\
\
def main():\
    init_db()\
    app = Application.builder().token(TOKEN).build()\
    app.add_handler(CommandHandler("start", start))\
    app.add_handler(CommandHandler("history", history))\
    app.add_handler(CommandHandler("report", report))\
    app.add_handler(MessageHandler(filters.\
VOICE, handle_voice))\
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))\
    app.run_polling()\
\
if __name__ == "__main__":\
    main()}