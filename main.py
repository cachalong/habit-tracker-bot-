import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask
import json
import time

TOKEN = '8238629742:AAGUzCWKz4WpR4f08-XRaij6uMHCKl-kX20'  # Вставь сюда свой токен
bot = telebot.TeleBot(TOKEN)

user_habits = {}
habit_log = {}
reminders = {}
user_timezones = {}

DATA_FILE = "data.json"

def load_data():
    global user_habits, habit_log, reminders, user_timezones
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            user_habits = data.get("user_habits", {})
            habit_log = data.get("habit_log", {})
            reminders = data.get("reminders", {})
            user_timezones = data.get("user_timezones", {})
    except FileNotFoundError:
        user_habits = {}
        habit_log = {}
        reminders = {}
        user_timezones = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "user_habits": user_habits,
            "habit_log": habit_log,
            "reminders": reminders,
            "user_timezones": user_timezones
        }, f, indent=4)

load_data()

app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

def get_user_habits(user_id):
    return user_habits.get(str(user_id), [])

def save_user_habit(user_id, habit):
    user_habits.setdefault(str(user_id), [])
    if habit not in user_habits[str(user_id)]:
        user_habits[str(user_id)].append(habit)

def remove_user_habit(user_id, habit):
    uid = str(user_id)
    if uid in user_habits and habit in user_habits[uid]:
        user_habits[uid].remove(habit)
    if uid in reminders and habit in reminders[uid]:
        del reminders[uid][habit]

def mark_habit_done(user_id, habit):
    uid = str(user_id)
    habit_log.setdefault(uid, {})
    now = datetime.utcnow() + timedelta(hours=user_timezones.get(uid, 0))
    key = f"{habit}_{now.date().isoformat()}"
    habit_log[uid][key] = True

def is_habit_done(user_id, habit, day=None):
    uid = str(user_id)
    if day is None:
        now = datetime.utcnow() + timedelta(hours=user_timezones.get(uid, 0))
        day = now.date().isoformat()
    key = f"{habit}_{day}"
    return habit_log.get(uid, {}).get(key, False)

def add_reminder(user_id, habit, time_str):
    uid = str(user_id)
    reminders.setdefault(uid, {})
    reminders[uid].setdefault(habit, [])
    if time_str not in reminders[uid][habit]:
        reminders[uid][habit].append(time_str)

def remove_reminder(user_id, habit, time_str):
    uid = str(user_id)
    if uid in reminders and habit in reminders[uid] and time_str in reminders[uid][habit]:
        reminders[uid][habit].remove(time_str)
        # Если после удаления список пустой, убираем привычку из reminders
        if not reminders[uid][habit]:
            del reminders[uid][habit]

def main_menu_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Добавить привычку", callback_data="add_menu"),
        InlineKeyboardButton("✅ Отметить привычку", callback_data="mark"),
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
        InlineKeyboardButton("🗑 Удалить привычку", callback_data="delete"),
        InlineKeyboardButton("⏰ Напоминания", callback_data="remind"),
        InlineKeyboardButton("🌍 Установить часовой пояс", callback_data="set_timezone"),
    )
    return markup

preset_habits = ["Пить воду", "Бег", "Медитировать", "Чтение книги", "Спорт"]

@bot.message_handler(commands=['start', 'menu'])
def send_menu(message):
    bot.send_message(message.chat.id, "Выбери действие:", reply_markup=main_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data == "add_menu")
def add_menu(call):
    markup = InlineKeyboardMarkup()
    for habit in preset_habits:
        markup.add(InlineKeyboardButton(habit, callback_data=f"add_{habit}"))
    markup.add(InlineKeyboardButton("Своя привычка", callback_data="add_custom"))
    markup.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    bot.edit_message_text("Выбери привычку для добавления или введи свою:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_custom")
def add_custom_habit_start(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Напиши название своей привычки:")
    bot.register_next_step_handler(msg, save_custom_habit)

def save_custom_habit(message):
    habit = message.text.strip()
    if habit == "":
        bot.send_message(message.chat.id, "Название привычки не может быть пустым. Попробуй ещё раз через /menu")
        return
    save_user_habit(message.chat.id, habit)
    save_data()
    bot.send_message(message.chat.id, f"Привычка «{habit}» добавлена!")
    bot.send_message(message.chat.id, "Вернись в меню:", reply_markup=main_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
def add_habit(call):
    habit = call.data[4:]
    save_user_habit(call.message.chat.id, habit)
    save_data()
    bot.answer_callback_query(call.id, f"Привычка «{habit}» добавлена!")
    bot.edit_message_text(f"Привычка «{habit}» добавлена!", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_action(call):
    bot.edit_message_text("Действие отменено.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data == "delete")
def delete_habit_start(call):
    habits = get_user_habits(call.message.chat.id)
    if not habits:
        bot.answer_callback_query(call.id, "Нет привычек для удаления.")
        return
    markup = InlineKeyboardMarkup()
    for h in habits:
        markup.add(InlineKeyboardButton(h, callback_data=f"delete_{h}"))
    markup.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    bot.edit_message_text("Выбери привычку для удаления:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def delete_habit_confirm(call):
    habit = call.data[len("delete_"):]
    remove_user_habit(call.message.chat.id, habit)
    save_data()
    bot.answer_callback_query(call.id, f"Привычка «{habit}» удалена.")
    bot.edit_message_text("Привычка удалена.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data == "mark")
def mark_habit_start(call):
    habits = get_user_habits(call.message.chat.id)
    if not habits:
        bot.answer_callback_query(call.id, "Нет привычек для отметки.")
        return
    markup = InlineKeyboardMarkup()
    for h in habits:
        markup.add(InlineKeyboardButton(h, callback_data=f"mark_{h}"))
    markup.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    bot.edit_message_text("Выбери привычку, которую выполнил сегодня:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("mark_"))
def mark_habit_done_callback(call):
    habit = call.data[len("mark_"):]
    mark_habit_done(call.message.chat.id, habit)
    save_data()
    bot.answer_callback_query(call.id, f"Отметил привычку «{habit}» за сегодня.")
    bot.edit_message_text(f"Отметил привычку «{habit}» за сегодня.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data == "stats")
def show_stats_menu(call):
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("За день", callback_data="stats_day"),
        InlineKeyboardButton("За неделю", callback_data="stats_week"),
        InlineKeyboardButton("За месяц", callback_data="stats_month"),
        InlineKeyboardButton("Назад", callback_data="cancel")
    )
    bot.edit_message_text("Выбери период для статистики:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("stats_"))
def show_stats(call):
    user_id = str(call.message.chat.id)
    period = call.data[len("stats_"):]
    habits = get_user_habits(user_id)
    if not habits:
        bot.answer_callback_query(call.id, "Нет привычек для статистики.")
        return

    now = datetime.utcnow() + timedelta(hours=user_timezones.get(user_id, 0))

    def daterange(start_date, end_date):
        for n in range(int((end_date - start_date).days) + 1):
            yield start_date + timedelta(n)

    if period == "day":
        start_date = now.date()
    elif period == "week":
        start_date = now.date() - timedelta(days=now.weekday())  # Пн этой недели
    elif period == "month":
        start_date = now.date().replace(day=1)
    else:
        start_date = now.date()

    end_date = now.date()

    result = f"📊 Статистика за {period}:\n"
    for h in habits:
        done_count = 0
        total_days = 0
        for single_date in daterange(start_date, end_date):
            day_str = single_date.isoformat()
            total_days += 1
            if is_habit_done(user_id, h, day_str):
                done_count += 1
        percent = int(done_count / total_days * 100) if total_days > 0 else 0
        result += f"{h}: {done_count}/{total_days} ({percent}%)\n"

    bot.edit_message_text(result, call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data == "remind")
def remind_start(call):
    habits = get_user_habits(call.message.chat.id)
    if not habits:
        bot.answer_callback_query(call.id, "Нет привычек для напоминаний.")
        return
    markup = InlineKeyboardMarkup()
    for h in habits:
        markup.add(InlineKeyboardButton(h, callback_data=f"remind_{h}"))
    markup.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    bot.edit_message_text("Выбери привычку для настройки напоминаний:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("remind_") and ("|" not in call.data))
def remind_time_menu(call):
    habit = call.data[len("remind_"):]
    bot.answer_callback_query(call.id)
    user_id = str(call.message.chat.id)
    times = reminders.get(user_id, {}).get(habit, [])
    markup = InlineKeyboardMarkup()
    # Кнопки для удаления каждого напоминания
    for t in times:
        markup.add(InlineKeyboardButton(f"Удалить {t}", callback_data=f"remind_del|{habit}|{t}"))
    markup.add(InlineKeyboardButton("Добавить новое время", callback_data=f"remind_add|{habit}"))
    markup.add(InlineKeyboardButton("Назад", callback_data="remind"))
    bot.edit_message_text(f"Текущие напоминания для «{habit}»:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("remind_del|"))
def delete_reminder_callback(call):
    _, habit, time_str = call.data.split("|")
    user_id = call.message.chat.id
    remove_reminder(user_id, habit, time_str)
    save_data()
    bot.answer_callback_query(call.id, f"Напоминание {time_str} удалено для привычки «{habit}».")
    # Обновляем меню напоминаний для этой привычки
    remind_time_menu(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("remind_add|"))
def add_reminder_callback(call):
    habit = call.data[len("remind_add|"):]
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id,
        f"Напиши время для нового напоминания по привычке «{habit}» в формате ЧЧ:ММ (например, 08:30):")
    bot.register_next_step_handler(msg, process_time_input, habit)

def process_time_input(message, habit):
    time_str = message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат времени! Попробуй заново через /menu")
        return
    add_reminder(message.chat.id, habit, time_str)
    save_data()
    bot.send_message(message.chat.id, f"Напоминание для «{habit}» установлено на {time_str}.")
    bot.send_message(message.chat.id, "Вернись в меню:", reply_markup=main_menu_markup())

@bot.callback_query_handler(func=lambda call: call.data == "set_timezone")
def set_timezone_start(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, "Напиши своё смещение от UTC в часах (например, +3 или -1):")
    bot.register_next_step_handler(msg, process_timezone)

def process_timezone(message):
    tz_text = message.text.strip()
    try:
        tz_offset = int(tz_text)
        user_timezones[str(message.chat.id)] = tz_offset
        save_data()
        bot.send_message(message.chat.id, f"Часовой пояс установлен: UTC{tz_offset:+d}")
    except:
        bot.send_message(message.chat.id, "Некорректный ввод. Пиши число, например +3 или -1")

def cancel(call):
    bot.edit_message_text("Действие отменено.", call.message.chat.id, call.message.message_id, reply_markup=main_menu_markup())

bot.callback_query_handler(func=lambda call: call.data == "cancel")(cancel)

def reminder_checker():
    while True:
        now_utc = datetime.utcnow()
        for user_id, habits_dict in reminders.items():
            try:
                tz_offset = user_timezones.get(user_id, 0)  # По умолчанию UTC+0
                now_local = now_utc + timedelta(hours=tz_offset)
                current_time = now_local.strftime("%H:%M")
                for habit, times in habits_dict.items():
                    if current_time in times:
                        bot.send_message(int(user_id), f"⏰ Напоминание: пора выполнить привычку «{habit}»!")
            except Exception as e:
                print(f"Ошибка напоминания для {user_id}: {e}")
        time.sleep(60)

keep_alive()
Thread(target=reminder_checker, daemon=True).start()

bot.infinity_polling()
