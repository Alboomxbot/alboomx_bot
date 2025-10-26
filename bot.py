import os
import csv
import re
import json
import base64
from datetime import datetime
import telebot
from telebot import types
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────
#  Загрузка конфигурации
# ─────────────────────────────────────────────────────
load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
SITE_URL = os.getenv("SITE_URL")
ALBUMS_URL = os.getenv("ALBUMS_URL")  # 🔗 новый сайт для выпускных альбомов
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# ─────────────────────────────────────────────────────
#  Авторизация Google Sheets через Base64-переменную
# ─────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

b64 = os.getenv("SERVICE_ACCOUNT_DATA_B64")
if not b64:
    raise RuntimeError("❌ Переменная SERVICE_ACCOUNT_DATA_B64 не установлена в Render!")

try:
    service_account_json = base64.b64decode(b64).decode("utf-8")
    service_account_info = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    print("✅ Подключение к Google Sheets успешно")
except Exception as e:
    print("❌ Ошибка подключения к Google Sheets:", e)
    sheet = None

# ─────────────────────────────────────────────────────
#  CSV-резерв (на случай сбоя)
# ─────────────────────────────────────────────────────
if not os.path.exists("clients.csv"):
    with open("clients.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Имя", "Телефон", "Username", "UserID", "Дата", "Статус", "Комментарий", "Менеджер"])

# ─────────────────────────────────────────────────────
#  Инициализация Telegram-бота
# ─────────────────────────────────────────────────────
bot = telebot.TeleBot(TOKEN)

# ─────────────────────────────────────────────────────
#  Главное меню
# ─────────────────────────────────────────────────────
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📸 Печать фото", "📚 Фотокниги")
    markup.row("🎓 Выпускные альбомы", "🔥 Акции и скидки")
    markup.row("💬 Связаться с оператором")
    return markup

# ─────────────────────────────────────────────────────
#  Команда /start
# ─────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────
#  Обработка кнопок
# ─────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: True)
def handle_message(message):
    if message.text == "📸 Печать фото":
        bot.send_message(message.chat.id, f"📸 Отлично! Загрузите фото:\n👉 {SITE_URL}/products/view/photoprint")
    elif message.text == "📚 Фотокниги":
        bot.send_message(message.chat.id, f"📚 Наши фотокниги:\n👉 {SITE_URL}/products/view/photobook")
    elif message.text == "🎓 Выпускные альбомы":
        bot.send_message(
            message.chat.id,
            "🎓 Наш новый проект выпускных альбомов и виньеток!\n"
            "Посмотри примеры и оформи заказ здесь 👇\n"
            f"👉 {ALBUMS_URL}"
        )
    elif message.text == "🔥 Акции и скидки":
        bot.send_message(message.chat.id, "🔥 Акция недели: Распечатай 30 фото — получи 5 бесплатно!")
    elif message.text == "💬 Связаться с оператором":
        msg = bot.send_message(message.chat.id, "📞 Напиши своё имя и телефон (например: Анна, +77001234567):")
        bot.register_next_step_handler(msg, get_contact)
    else:
        bot.send_message(message.chat.id, "Выбери пункт меню 👇", reply_markup=main_menu())

# ─────────────────────────────────────────────────────
#  Получение контактов
# ─────────────────────────────────────────────────────
def get_contact(message):
    contact = message.text.strip()
    username = message.from_user.username or "нет username"
    user_id = message.from_user.id

    phone_pattern = r"\+?\d[\d\s\-\(\)]{6,}"
    if not re.search(phone_pattern, contact):
        msg = bot.send_message(message.chat.id, "❗ Укажите номер телефона (пример: +77001234567):")
        bot.register_next_step_handler(msg, get_contact)
        return

    # Резервное сохранение в CSV
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

    # Добавление в Google Sheets
    if sheet:
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
            error_text = f"⚠️ Ошибка при добавлении в Google Sheets:\n{e}"
            bot.send_message(ADMIN_ID, error_text)

    # Подтверждение пользователю
    bot.send_message(message.chat.id, "✅ Спасибо! Мы скоро свяжемся с вами 💬", reply_markup=main_menu())

    # Уведомление админу
    bot.send_message(
        ADMIN_ID,
        f"📬 Новая заявка:\n{contact}\nОт: @{username}\n\nИзменить статус можно командой:\n"
        f"`/lead {user_id}`",
        parse_mode="Markdown"
    )

# ─────────────────────────────────────────────────────
#  Управление лидами (только админ)
# ─────────────────────────────────────────────────────
@bot.message_handler(commands=["lead"])
def manage_lead(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Только администратор может изменять статусы.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❗ Использование: /lead <UserID>")
            return

        target_id = parts[1]
        rows = sheet.get_all_values()
        found_row = None

        for i, row in enumerate(rows, start=1):
            if str(row[3]) == target_id:
                found_row = i
                break

        if not found_row:
            bot.send_message(message.chat.id, "⚠️ Лид с таким UserID не найден.")
            return

        lead_data = rows[found_row - 1]
        name, phone, username, user_id, date, status, comment, manager = lead_data

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🟦 Новый", callback_data=f"status_{found_row}_Новая"),
            types.InlineKeyboardButton("🟨 В работе", callback_data=f"status_{found_row}_В работе"),
            types.InlineKeyboardButton("🟩 Завершён", callback_data=f"status_{found_row}_Завершён"),
            types.InlineKeyboardButton("🟥 Отказ", callback_data=f"status_{found_row}_Отказ")
        )

        bot.send_message(
            message.chat.id,
            f"📋 Лид найден:\n"
            f"👤 {name}\n📞 {phone}\n💬 @{username}\n🕒 {date}\n📍 Статус: {status}",
            reply_markup=markup
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}")

# ─────────────────────────────────────────────────────
#  Изменение статуса лида
# ─────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: call.data.startswith("status_"))
def change_status(call):
    try:
        parts = call.data.split("_")
        row_index = int(parts[1])
        new_status = parts[2]

        sheet.update_cell(row_index, 6, new_status)
        sheet.update_cell(row_index, 8, "Админ")
        bot.answer_callback_query(call.id, f"✅ Статус изменён на: {new_status}")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, f"✅ Статус лида обновлён: {new_status}")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Ошибка при изменении статуса: {e}")

# ─────────────────────────────────────────────────────
#  Запуск
# ─────────────────────────────────────────────────────
try:
    bot.send_message(ADMIN_ID, "✅ Бот успешно запущен и подключён к Google Sheets!")
except Exception:
    print("⚠️ Не удалось отправить сообщение админу.")

print("✅ Бот запущен и слушает сообщения...")
bot.polling(none_stop=True)
