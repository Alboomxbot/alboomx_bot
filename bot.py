import os
import csv
import re
import json
import base64
import threading
from datetime import datetime
from flask import Flask, render_template_string
import telebot
from telebot import types
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ───────────────────────────────────────────────
# 🌐 Flask web server for Render/UptimeRobot + визитка
# ───────────────────────────────────────────────
app = Flask(__name__)

@app.route('/')
def home():
    html = """
    <html>
      <head>
        <meta charset="utf-8">
        <title>AlboomX Bot</title>
        <style>
          body {
            background: linear-gradient(135deg, #1b335f, #071226);
            color: white;
            font-family: 'Inter', sans-serif;
            text-align: center;
            padding-top: 100px;
          }
          h1 { font-size: 2em; margin-bottom: 0.3em; }
          p { font-size: 1.2em; opacity: 0.85; }
          a {
            color: #ffd700;
            text-decoration: none;
            font-weight: 600;
          }
          a:hover { text-decoration: underline; }
        </style>
      </head>
      <body>
        <h1>✅ AlboomX бот работает 24/7</h1>
        <p>📸 Печать фото &nbsp;•&nbsp; 📚 Фотокниги &nbsp;•&nbsp; 🎓 Выпускные альбомы</p>
        <p>🌐 <a href="https://alboomx.com" target="_blank">alboomx.com</a></p>
      </body>
    </html>
    """
    return render_template_string(html)

def run_web():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_web).start()

# ───────────────────────────────────────────────
# ⚙️ Load configuration
# ───────────────────────────────────────────────
load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
SITE_URL = os.getenv("SITE_URL")
ALBUMS_URL = os.getenv("ALBUMS_URL")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# ───────────────────────────────────────────────
# ☁️ Google Sheets via Base64 credentials
# ───────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

b64_data = os.getenv("SERVICE_ACCOUNT_DATA_B64")
if not b64_data:
    raise RuntimeError("❌ Переменная SERVICE_ACCOUNT_DATA_B64 не установлена в Render!")

try:
    service_account_json = base64.b64decode(b64_data).decode('utf-8')
    service_account_info = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    print("✅ Подключение к Google Sheets успешно")
except Exception as e:
    raise RuntimeError(f"❌ Ошибка подключения к Google Sheets: {e}")

# ───────────────────────────────────────────────
# 🗂 CSV backup
# ───────────────────────────────────────────────
if not os.path.exists("clients.csv"):
    with open("clients.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Имя", "Телефон", "Username", "UserID", "Дата", "Статус", "Комментарий", "Менеджер"])

# ───────────────────────────────────────────────
# 🤖 Telegram Bot Setup
# ───────────────────────────────────────────────
bot = telebot.TeleBot(TOKEN)

# ───────────────────────────────────────────────
# 📍 Главное меню
# ───────────────────────────────────────────────
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📸 Печать фото", "📚 Фотокниги")
    markup.row("🎓 Выпускные альбомы", "🔥 Акции и скидки")
    markup.row("💬 Связаться с оператором")
    return markup

# ───────────────────────────────────────────────
# 🎉 /start
# ───────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def start(message):
    first_name = message.from_user.first_name or "Клиент"
    text = (
        f"👋 Привет, {first_name}!\n\n"
        "Я помощник сервиса *AlboomX*.\n"
        "Помогу напечатать фото, сделать фотокнигу или выпускной альбом.\n\n"
        "Выбери нужный раздел 👇"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

# ───────────────────────────────────────────────
# 🧭 Обработка кнопок
# ───────────────────────────────────────────────
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    if message.text == "📸 Печать фото":
        bot.send_message(message.chat.id, f"📸 Отлично! Загрузите фото:\n👉 {SITE_URL}/products/view/photoprint")
    elif message.text == "📚 Фотокниги":
        bot.send_message(message.chat.id, f"📚 Наши фотокниги:\n👉 {SITE_URL}/products/view/photobook")
    elif message.text == "🎓 Выпускные альбомы":
        bot.send_message(message.chat.id, f"🎓 Примеры выпускных альбомов здесь:\n👉 {ALBUMS_URL}")
    elif message.text == "🔥 Акции и скидки":
        bot.send_message(message.chat.id, "🔥 Акция недели: Распечатай 30 фото — получи 5 бесплатно!")
    elif message.text == "💬 Связаться с оператором":
        msg = bot.send_message(message.chat.id, "📞 Напиши своё имя и телефон (например: Анна, +77001234567):")
        bot.register_next_step_handler(msg, get_contact)
    else:
        bot.send_message(message.chat.id, "Выбери пункт меню 👇", reply_markup=main_menu())

# ───────────────────────────────────────────────
# 📩 Контакт клиента
# ───────────────────────────────────────────────
def get_contact(message):
    contact = message.text.strip()
    username = message.from_user.username or "нет username"
    user_id = message.from_user.id

    phone_pattern = r"\+?\d[\d\s\-\(\)]{6,}"
    if not re.search(phone_pattern, contact):
        msg = bot.send_message(message.chat.id, "❗ Укажите номер телефона (пример: +77001234567):")
        bot.register_next_step_handler(msg, get_contact)
        return

    with open("clients.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            contact.split(",")[0],
            contact,
            username,
            user_id,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            "Новая",
            "",
            "—"
        ])

    try:
        sheet.append_row([
            contact.split(",")[0],
            contact,
            username,
            user_id,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            "Новая",
            "",
            "—"
        ])
    except Exception as e:
        bot.send_message(ADMIN_ID, f"⚠️ Ошибка при добавлении в Google Sheets:\n{e}")

    bot.send_message(message.chat.id, "✅ Спасибо! Мы скоро свяжемся с вами 💬", reply_markup=main_menu())
    bot.send_message(ADMIN_ID, f"📬 Новая заявка:\n{contact}\nОт: @{username}")

# ───────────────────────────────────────────────
# 🚀 Запуск
# ───────────────────────────────────────────────
bot.send_message(ADMIN_ID, "✅ Бот успешно запущен и подключён к Google Sheets!")
print("✅ Бот запущен и слушает сообщения...")
bot.polling(none_stop=True)
