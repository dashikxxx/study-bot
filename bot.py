import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from aiogram.dispatcher.middlewares.base import BaseMiddleware

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8911975208:AAH8qae_slOlQOD1h3o-r2EHOe0d4nd5r-c" 
GROQ_API_KEY = "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"
ADMIN_ID = 1014319922 

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS subjects
                      (id INTEGER PRIMARY KEY, name TEXT, teacher TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS lectures
                      (id INTEGER PRIMARY KEY, subject_id INTEGER, date TEXT, photo_ids TEXT, status TEXT DEFAULT 'new')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, is_blocked INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def save_user(user_id, username, first_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)", (user_id, username, first_name))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def is_user_blocked(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res and res[0] == 1

def get_users():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, is_blocked FROM users")
    res = cursor.fetchall()
    conn.close()
    return res

class BlockMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        if user_id == ADMIN_ID:
            return await handler(event, data)
        if is_user_blocked(user_id):
            if isinstance(event, types.CallbackQuery):
                await event.answer("❌ Вы были заблокированы администратором.", show_alert=True)
            else:
                await event.answer("❌ Вы были заблокированы администратором.")
            return
        return await handler(event, data)

dp = Dispatcher(storage=MemoryStorage())
dp.message.outer_middleware(BlockMiddleware())
dp.callback_query.outer_middleware(BlockMiddleware())

def get_subjects():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM subjects")
    res = cursor.fetchall()
    conn.close()
    return res

def get_lectures(subject_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, status FROM lectures WHERE subject_id = ? ORDER BY date ASC", (subject_id,))
    res = cursor.fetchall()
    conn.close()
    return res

def get_subject_info(subject_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, teacher FROM subjects WHERE id = ?", (subject_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def get_lecture_info(lecture_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT date, photo_ids FROM lectures WHERE id = ?", (lecture_id,))
    res = cursor.fetchone()
    conn.close()
    return res

# --- СОСТОЯНИЯ ---
class AddSubject(StatesGroup):
    waiting_for_name = State()
    waiting_for_teacher = State()

class AddLecture(StatesGroup):
    waiting_for_subject = State()
    waiting_for_date = State()
    waiting_for_photo = State()

class EditSubject(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_teacher = State()

class EditLecture(StatesGroup):
    waiting_for_new_date = State()
    waiting_for_new_photo = State()

class ContactAdmin(StatesGroup):
    waiting_for_message = State()

class ReplyToUser(StatesGroup):
    waiting_for_reply = State()

bot = Bot(token=BOT_TOKEN)

# --- КЛАВИАТУРЫ ---
def main_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 В меню"), KeyboardButton(text="✉️ Связаться с админом")]],
        resize_keyboard=True
    )

def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена"), KeyboardButton(text="🏠 В меню")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def done_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Готово")],
            [KeyboardButton(text="❌ Отмена"), KeyboardButton(text="🏠 В меню")]
        ],
        resize_keyboard=True
    )

def main_menu(user_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔔 Ближайшая лекция", callback_data="nearest_lecture")])
    subjects = get_subjects()
    for subj_id, name in subjects:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=name, callback_data=f"subj_{subj_id}")])
    if user_id == ADMIN_ID:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel")])
    return keyboard

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    is_new = save_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    if is_new and message.from_user.id != ADMIN_ID:
        user_link = f"@{message.from_user.username}" if message.from_user.username else "без username"
        try:
            await bot.send_message(ADMIN_ID, f"🔔 **Новый пользователь!**\nИмя: {message.from_user.first_name}\nЮзернейм: {user_link}\nID: `{message.from_user.id}`", parse_mode="Markdown")
        except Exception:
            pass

    if message.from_user.id != ADMIN_ID and is_user_blocked(message.from_user.id):
        return

    await message.answer("Привет! Выбери предмет, чтобы посмотреть лекции:", reply_markup=main_menu(message.from_user.id))
    await message.answer("Используй кнопки ниже для навигации.", reply_markup=main_reply_keyboard())

@dp.message(F.text == "❌ Отмена")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено. Возвращаемся в меню:", reply_markup=main_menu(message.from_user.id))

@dp.message(F.text == "🏠 В меню")
async def go_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню. Выбери предмет:", reply_markup=main_menu(message.from_user.id))

# --- СВЯЗЬ С АДМИНОМ ---
@dp.message(F.text == "✉️ Связаться с админом")
async def contact_admin(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Вы и есть администратор :)")
        return
    await state.set_state(ContactAdmin.waiting_for_message)
    await message.answer("Напишите ваше сообщение для администратора (текст или фото).", reply_markup=cancel_keyboard())

@dp.message(ContactAdmin.waiting_for_message)
async def send_message_to_admin(message: types.Message, state: FSMContext):
    user = message.from_user
    user_link = f"@{user.username}" if user.username else f"ID: {user.id}"
    try:
        reply_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user.id}")]])
        if message.text:
            await bot.send_message(ADMIN_ID, f"✉️ **Сообщение от {user_link}** (ID: {user.id}):\n\n{message.text}", reply_markup=reply_kb, parse_mode="Markdown")
        elif message.photo:
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=f"✉️ **Фото от {user_link}** (ID: {user.id})", reply_markup=reply_kb, parse_mode="Markdown")
        await message.answer("✅ Ваше сообщение отправлено администратору!", reply_markup=main_reply_keyboard())
        await state.clear()
    except Exception:
        await message.answer("❌ Не удалось отправить сообщение.")
        await state.clear()

@dp.callback_query(F.data.startswith("reply_"))
async def start_reply_to_user(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[1]
    await state.update_data(reply_user_id=user_id)
    await state.set_state(ReplyToUser.waiting_for_reply)
    await callback.message.answer(f"Введите ответ для пользователя (ID: {user_id}):", reply_markup=cancel_keyboard())
    await callback.answer()

@dp.message(ReplyToUser.waiting_for_reply)
async def process_admin_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_user_id')
    try:
        if message.text:
            await bot.send_message(user_id, f"👑 **Ответ от администратора:**\n\n{message.text}", parse_mode="Markdown")
        elif message.photo:
            await bot.send_photo(user_id, message.photo[-1].file_id, caption="👑 **Фото от администратора**")
        await message.answer("✅ Ответ отправлен!", reply_markup=main_reply_keyboard())
    except Exception:
        await message.answer("❌ Не удалось отправить.", reply_markup=main_reply_keyboard())
    await state.clear()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
    blocked_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM subjects")
    total_subjects = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM lectures")
    total_lectures = cursor.fetchone()[0]
    conn.close()
    text = (f"📊 **Статистика бота:**\n\n👥 Всего пользователей: {total_users}\n🚫 Заблокировано: {blocked_users}\n✅ Активных: {total_users - blocked_users}\n\n📚 Предметов: {total_subjects}\n📝 Лекций: {total_lectures}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "nearest_lecture")
async def nearest_lecture(callback: types.CallbackQuery):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    today = datetime.now().strftime("%d.%m.%Y")
    cursor.execute("SELECT id, subject_id, date FROM lectures WHERE date >= ? ORDER BY date ASC LIMIT 1", (today,))
    res = cursor.fetchone()
    conn.close()
    if res:
        lect_id, subj_id, date = res
        subj_name = get_subject_info(subj_id)[0]
        await callback.message.edit_text(f"🔔 Ближайшая лекция: **{subj_name}**\n📅 Дата: {date}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Посмотреть", callback_data=f"lect_{lect_id}")],[InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_main")]]), parse_mode="Markdown")
    else:
        await callback.message.edit_text("Ура! Ближайших лекций пока нет 🎉", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_main")]]))

@dp.callback_query(F.data.startswith("subj_"))
async def show_dates(callback: types.CallbackQuery):
    subj_id = int(callback.data.split("_")[1])
    dates = get_lectures(subj_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    if not dates:
        await callback.message.edit_text("По этому предмету пока нет лекций.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]]))
        return
    for lect_id, date, status in dates:
        prefix = "✅ " if status == "read" else "📅 "
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{prefix}{date}", callback_data=f"lect_{lect_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_main")])
    await callback.message.edit_text("Выбери дату лекции:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("lect_"))
async def show_lecture(callback: types.CallbackQuery):
    lect_id = callback.data.split("_")[1]
    info = get_lecture_info(lect_id)
    if info and info[1]:
        photo_ids_str, date, status = info[1], info[0], None
        
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM lectures WHERE id = ?", (lect_id,))
        status = cursor.fetchone()[0]
        conn.close()
        
        photo_ids = photo_ids_str.split(',')
        mark_kb = InlineKeyboardMarkup(inline_keyboard=[])
        
        if status != "read":
            mark_kb.inline_keyboard.append([InlineKeyboardButton(text="✅ Отметить как прочитанное", callback_data=f"markread_{lect_id}")])
        else:
            mark_kb.inline_keyboard.append([InlineKeyboardButton(text="↩️ Снять отметку", callback_data=f"unmarkread_{lect_id}")])
            
        caption = f"Лекция за {date}"
        if len(photo_ids) > 1:
            media_group = []
            for i, p_id in enumerate(photo_ids):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=p_id, caption=caption))
                else:
                    media_group.append(InputMediaPhoto(media=p_id))
            await callback.message.answer_media_group(media=media_group)
            await callback.message.answer("Действия с лекцией:", reply_markup=mark_kb)
        else:
            await callback.message.answer_photo(photo=photo_ids[0], caption=caption, reply_markup=mark_kb)
        
        await callback.message.answer("Чтобы вернуться в меню, нажми кнопку «🏠 В меню» внизу.", reply_markup=main_reply_keyboard())
        await callback.answer()
    else:
        await callback.answer("Ошибка чтения лекции.")

@dp.callback_query(F.data.startswith("markread_"))
async def mark_as_read(callback: types.CallbackQuery):
    lect_id = callback.data.split("_")[1]
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE lectures SET status = 'read' WHERE id = ?", (lect_id,))
    conn.commit()
    conn.close()
    await callback.answer("Отлично! Лекция прочитана.")

@dp.callback_query(F.data.startswith("unmarkread_"))
async def unmark_as_read(callback: types.CallbackQuery):
    lect_id = callback.data.split("_")[1]
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE lectures SET status = 'new' WHERE id = ?", (lect_id,))
    conn.commit()
    conn.close()
    await callback.answer("Отметка снята.")

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("Выбери предмет:", reply_markup=main_menu(callback.from_user.id))
    await callback.message.answer("Главное меню", reply_markup=main_reply_keyboard())

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав!", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить предмет", callback_data="add_subject"), InlineKeyboardButton(text="✏️ Изменить предмет", callback_data="edit_subject_menu")],
        [InlineKeyboardButton(text="🖼 Добавить лекцию", callback_data="add_lecture"), InlineKeyboardButton(text="✏️ Изменить лекцию", callback_data="edit_lect_menu")],
        [InlineKeyboardButton(text="🗑 Удалить предмет", callback_data="del_subject_menu"), InlineKeyboardButton(text="🗑 Удалить лекцию", callback_data="del_lect_menu")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="view_users"), InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("⚙️ Админ-панель. Что делаем?", reply_markup=keyboard)

@dp.callback_query(F.data == "view_users")
async def view_users(callback: types.CallbackQuery):
    users = get_users()
    if not users:
        await callback.answer("Пользователей пока нет.", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    text = "👥 **Пользователи:**\n\n"
    for user_id, username, first_name, is_blocked in users:
        status = "🚫 Заблокирован" if is_blocked == 1 else "✅ Активен"
        user_link = f"@{username}" if username else "без username"
        text += f"• {first_name} ({user_link}) — {status}\n"
        if user_id != ADMIN_ID:
            btn_text = "🔓 Разблокировать" if is_blocked == 1 else "🚫 Заблокировать"
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{btn_text}: {first_name}", callback_data=f"toggleblock_{user_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    if len(text) > 4000:
        text = text[:3900] + "\n\n... (список обрезан)"
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("toggleblock_"))
async def toggle_block(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_blocked = CASE WHEN is_blocked = 1 THEN 0 ELSE 1 END WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await callback.answer("Статус пользователя изменен!")
    await view_users(callback)

# --- ЗАЩИТА ОТ СПАМА ПРИ ОЖИДАНИИ ТЕКСТА ---
@dp.callback_query(AddSubject.waiting_for_name)
async def ignore_callbacks_in_name(callback: types.CallbackQuery):
    await callback.answer("Пожалуйста, введи название текстом или нажми «❌ Отмена» внизу.")

@dp.callback_query(AddLecture.waiting_for_date)
async def ignore_callbacks_in_date(callback: types.CallbackQuery):
    await callback.answer("Пожалуйста, введи дату текстом или нажми «❌ Отмена».")

# --- ДОБАВЛЕНИЕ ПРЕДМЕТА ---
@dp.callback_query(F.data == "add_subject")
async def start_add_subject(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddSubject.waiting_for_name)
    await callback.message.answer("Введи название предмета (например: Математика):", reply_markup=cancel_keyboard())

@dp.message(AddSubject.waiting_for_name)
async def process_subj_name(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введи название текстом.")
        return
    await state.update_data(name=message.text)
    await state.set_state(AddSubject.waiting_for_teacher)
    await message.answer("Теперь введи имя преподавателя:", reply_markup=cancel_keyboard())

@dp.message(AddSubject.waiting_for_teacher)
async def process_subj_teacher(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введи имя текстом.")
        return
    data = await state.get_data()
    name = data['name']
    teacher = message.text
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO subjects (name, teacher) VALUES (?, ?)", (name, teacher))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(f"✅ Предмет '{name}' (Препод: {teacher}) добавлен!", reply_markup=main_menu(message.from_user.id))
    await message.answer("Выбери действие:", reply_markup=main_reply_keyboard())

# --- ДОБАВЛЕНИЕ ЛЕКЦИИ ---
@dp.callback_query(F.data == "add_lecture")
async def start_add_lecture(callback: types.CallbackQuery, state: FSMContext):
    subjects = get_subjects()
    if not subjects:
        await callback.message.edit_text("Сначала добавь хотя бы один предмет!")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for subj_id, name in subjects:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=name, callback_data=f"addlect_{subj_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_panel")])
    await state.set_state(AddLecture.waiting_for_subject)
    await callback.message.edit_text("К какому предмету добавляем лекцию?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("addlect_"))
async def process_lect_subject(callback: types.CallbackQuery, state: FSMContext):
    subj_id = callback.data.split("_")[1]
    await state.update_data(subject_id=subj_id, photos=[])
    await state.set_state(AddLecture.waiting_for_date)
    await callback.message.answer("Введи дату лекции строго в формате **ДД.ММ.ГГГГ** (например, `15.09.2026`):", reply_markup=cancel_keyboard(), parse_mode="Markdown")

@dp.message(AddLecture.waiting_for_date)
async def process_lect_date(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Это не похоже на дату. Пожалуйста, введи дату текстом в формате ДД.ММ.ГГГГ.")
        return
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
    except ValueError:
        await message.answer("❌ Неверный формат даты! Пожалуйста, введи дату строго так: `15.09.2026`", parse_mode="Markdown")
        return
    await state.update_data(date=message.text)
    await state.set_state(AddLecture.waiting_for_photo)
    await message.answer("Отправь мне ФОТО (можно сразу альбомом/несколько штук), а затем нажми кнопку «✅ Готово»:", reply_markup=done_keyboard())

@dp.message(AddLecture.waiting_for_photo, F.photo)
async def process_lect_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if 'subject_id' not in data or 'date' not in data:
        await message.answer("⚠️ Контекст потерян. Начни добавление заново.")
        await state.clear()
        return
    photos = data.get('photos', [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"📸 Фото №{len(photos)} получено. Отправь следующее или нажми «✅ Готово».", reply_markup=done_keyboard())

@dp.message(AddLecture.waiting_for_photo, F.text == "✅ Готово")
async def finish_lecture_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    if not photos:
        await message.answer("Ты еще не отправила ни одного фото! Отправь фото или нажми «❌ Отмена».", reply_markup=done_keyboard())
        return
    subj_id = data['subject_id']
    date = data['date']
    photos_str = ",".join(photos)
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO lectures (subject_id, date, photo_ids) VALUES (?, ?, ?)", (subj_id, date, photos_str))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(f"✅ Лекция за {date} сохранена! Всего фото: {len(photos)}.", reply_markup=main_menu(message.from_user.id))
    await message.answer("Выбери действие:", reply_markup=main_reply_keyboard())

@dp.message(AddLecture.waiting_for_photo)
async def process_lect_wrong(message: types.Message):
    await message.answer("❌ Ой, я жду именно ФОТО! Отправь картинку или нажми «✅ Готово».", reply_markup=done_keyboard())

# --- РЕДАКТИРОВАНИЕ ЛЕКЦИИ ---
@dp.callback_query(F.data == "edit_lect_menu")
async def edit_lect_menu(callback: types.CallbackQuery):
    subjects = get_subjects()
    if not subjects:
        await callback.answer("Сначала добавь предметы!", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for subj_id, name in subjects:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=name, callback_data=f"edit_lect_subj_{subj_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    await callback.message.edit_text("В каком предмете изменить лекцию?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("edit_lect_subj_"))
async def edit_lect_choose_date(callback: types.CallbackQuery):
    subj_id = callback.data.split("_")[3]
    lectures = get_lectures(subj_id)
    if not lectures:
        await callback.answer("У этого предмета нет лекций!", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for lect_id, date, status in lectures:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=date, callback_data=f"editlec_{lect_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="edit_lect_menu")])
    await callback.message.edit_text("Какую лекцию изменить?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("editlec_"))
async def process_edit_lecture(callback: types.CallbackQuery, state: FSMContext):
    lect_id = callback.data.split("_")[1]
    info = get_lecture_info(lect_id)
    await state.update_data(lecture_id=lect_id, photos=[])
    await state.set_state(EditLecture.waiting_for_new_date)
    await callback.message.answer(f"Текущая дата: {info[0]}\nВведи НОВУЮ дату лекции (формат ДД.ММ.ГГГГ):", reply_markup=cancel_keyboard())

@dp.message(EditLecture.waiting_for_new_date)
async def edit_lect_date(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Пожалуйста, введи дату текстом.")
        return
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
    except ValueError:
        await message.answer("❌ Неверный формат! Введи дату как `15.09.2026`", parse_mode="Markdown")
        return
    await state.update_data(new_date=message.text)
    await state.set_state(EditLecture.waiting_for_new_photo)
    await message.answer("Отправь НОВЫЕ фото лекции (можно сразу альбомом), а затем нажми «✅ Готово»:", reply_markup=done_keyboard())

@dp.message(EditLecture.waiting_for_new_photo, F.photo)
async def edit_lect_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if 'lecture_id' not in data or 'new_date' not in data:
        await message.answer("⚠️ Контекст потерян. Начни изменение лекции заново.")
        await state.clear()
        return
    photos = data.get('photos', [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"📸 Новое фото №{len(photos)} получено. Отправь следующее или нажми «✅ Готово».", reply_markup=done_keyboard())

@dp.message(EditLecture.waiting_for_new_photo, F.text == "✅ Готово")
async def finish_edit_lecture_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    if not photos:
        await message.answer("Ты еще не отправила ни одного фото! Отправь фото или нажми «❌ Отмена».", reply_markup=done_keyboard())
        return
    lect_id = data['lecture_id']
    new_date = data['new_date']
    photos_str = ",".join(photos)
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE lectures SET date = ?, photo_ids = ?, status = 'new' WHERE id = ?", (new_date, photos_str, lect_id))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(f"✅ Лекция обновлена!\nНовая дата: {new_date}\nНовых фото: {len(photos)}.", reply_markup=main_menu(message.from_user.id))
    await message.answer("Выбери действие:", reply_markup=main_reply_keyboard())

@dp.message(EditLecture.waiting_for_new_photo)
async def edit_lect_wrong(message: types.Message):
    await message.answer("❌ Я жду именно ФОТО! Отправь картинку или нажми «✅ Готово».", reply_markup=done_keyboard())

# --- РЕДАКТИРОВАНИЕ ПРЕДМЕТА ---
@dp.callback_query(F.data == "edit_subject_menu")
async def edit_subject_menu(callback: types.CallbackQuery):
    subjects = get_subjects()
    if not subjects:
        await callback.answer("Нет предметов для изменения!", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for subj_id, name in subjects:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=name, callback_data=f"editsubj_{subj_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    await callback.message.edit_text("Какой предмет изменить?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("editsubj_"))
async def process_edit_subject(callback: types.CallbackQuery, state: FSMContext):
    subj_id = callback.data.split("_")[1]
    info = get_subject_info(subj_id)
    await state.update_data(subject_id=subj_id)
    await state.set_state(EditSubject.waiting_for_new_name)
    await callback.message.answer(f"Текущее название: {info[0]}\nВведи НОВОЕ название предмета:", reply_markup=cancel_keyboard())

@dp.message(EditSubject.waiting_for_new_name)
async def edit_subj_name(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введи текстом.")
        return
    await state.update_data(new_name=message.text)
    await state.set_state(EditSubject.waiting_for_new_teacher)
    await message.answer("Введи НОВОЕ имя преподавателя:", reply_markup=cancel_keyboard())

@dp.message(EditSubject.waiting_for_new_teacher)
async def edit_subj_teacher(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, введи текстом.")
        return
    data = await state.get_data()
    subj_id = data['subject_id']
    new_name = data['new_name']
    new_teacher = message.text
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE subjects SET name = ?, teacher = ? WHERE id = ?", (new_name, new_teacher, subj_id))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(f"✅ Предмет обновлен!\nНовое название: {new_name}\nНовый препод: {new_teacher}", reply_markup=main_menu(message.from_user.id))
    await message.answer("Выбери действие:", reply_markup=main_reply_keyboard())

# --- УДАЛЕНИЕ ПРЕДМЕТА ---
@dp.callback_query(F.data == "del_subject_menu")
async def del_subject_menu(callback: types.CallbackQuery):
    subjects = get_subjects()
    if not subjects:
        await callback.answer("Нет предметов для удаления.", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for subj_id, name in subjects:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"delsubj_{subj_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    await callback.message.edit_text("Какой предмет удалить? (Удалятся и все его лекции!)", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("delsubj_"))
async def process_del_subject(callback: types.CallbackQuery):
    subj_id = callback.data.split("_")[1]
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subjects WHERE id = ?", (subj_id,))
    cursor.execute("DELETE FROM lectures WHERE subject_id = ?", (subj_id,))
    conn.commit()
    conn.close()
    await callback.answer("Предмет и его лекции удалены!", show_alert=True)
    await admin_panel(callback)

# --- УДАЛЕНИЕ ЛЕКЦИИ ---
@dp.callback_query(F.data == "del_lect_menu")
async def del_lect_menu(callback: types.CallbackQuery):
    subjects = get_subjects()
    if not subjects:
        await callback.answer("Сначала добавь предметы!", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for subj_id, name in subjects:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=name, callback_data=f"del_lect_subj_{subj_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    await callback.message.edit_text("Из какого предмета удалить лекцию?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("del_lect_subj_"))
async def del_lect_choose_date(callback: types.CallbackQuery):
    subj_id = callback.data.split("_")[3]
    lectures = get_lectures(subj_id)
    if not lectures:
        await callback.answer("У этого предмета нет лекций!", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for lect_id, date, status in lectures:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {date}", callback_data=f"del_lect_{lect_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="del_lect_menu")])
    await callback.message.edit_text("Какую лекцию удалить?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("del_lect_") & ~F.data.startswith("del_lect_subj_") & ~F.data.startswith("del_lect_menu"))
async def process_del_lecture(callback: types.CallbackQuery):
    lect_id = callback.data.split("_")[2]
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lectures WHERE id = ?", (lect_id,))
    conn.commit()
    conn.close()
    await callback.answer("Лекция удалена!", show_alert=True)
    await admin_panel(callback)

from aiohttp import web

async def web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is alive!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000) # Render по умолчанию ждет порт 10000
    await site.start()

async def main():
    init_db()
    print("Бот запущен и готов к работе!")
    asyncio.create_task(web_server()) # Запускаем фейковый сайт в фоне
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
