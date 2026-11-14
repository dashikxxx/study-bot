import asyncio
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from supabase import create_client, Client

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8911975208:AAH8qae_slOlQOD1h3o-r2EHOe0d4nd5r-c"
ADMIN_ID = 1014319922 

SUPABASE_URL = "https://hzfkuyskyjdjzidffgmw.supabase.co"
SUPABASE_KEY = "sb_publishable_syBgnqOnyh7mSc85tKKmkA_azXMWFec"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- ФУНКЦИИ БАЗЫ ДАННЫХ (SUPABASE) ---
def get_subjects():
    res = supabase.table('subjects').select('*').execute()
    return [(item['id'], item['name']) for item in res.data]

def get_lectures(subject_id):
    res = supabase.table('lectures').select('*').eq('subject_id', subject_id).order('id').execute()
    return [(item['id'], item['date'], item['status']) for item in res.data]

def get_subject_info(subject_id):
    res = supabase.table('subjects').select('name, teacher').eq('id', subject_id).execute()
    if res.data:
        return res.data[0]['name'], res.data[0]['teacher']
    return None

def get_lecture_info(lecture_id):
    res = supabase.table('lectures').select('date, photo_ids').eq('id', lecture_id).execute()
    if res.data:
        return res.data[0]['date'], res.data[0]['photo_ids']
    return None

def save_user(user_id, username, first_name):
    try:
        res = supabase.table('users').select('user_id').eq('user_id', user_id).execute()
        if not res.data:
            # Если username None, сохраняем пустую строку, чтобы не было ошибки
            uname = username if username else ""
            fname = first_name if first_name else "Пользователь"
            supabase.table('users').insert({"user_id": user_id, "username": uname, "first_name": fname}).execute()
            return True
    except Exception as e:
        print(f"Ошибка сохранения пользователя: {e}")
    return False

def is_user_blocked(user_id):
    res = supabase.table('users').select('is_blocked').eq('user_id', user_id).execute()
    return res.data and res.data[0]['is_blocked'] == 1

def get_users():
    res = supabase.table('users').select('*').execute()
    return [(u['user_id'], u['username'], u['first_name'], u['is_blocked']) for u in res.data]

# --- MIDDLEWARE ДЛЯ БЛОКИРОВКИ ---
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

dp.message.outer_middleware(BlockMiddleware())
dp.callback_query.outer_middleware(BlockMiddleware())

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

# --- КЛАВИАТУРЫ ---
def main_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 В меню"), KeyboardButton(text="🔄 Перезапустить")],
            [KeyboardButton(text="✉️ Связаться с админом")]
        ], 
        resize_keyboard=True
    )

def cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена"), KeyboardButton(text="🏠 В меню")]], resize_keyboard=True, one_time_keyboard=True)

def done_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Готово")], [KeyboardButton(text="❌ Отмена"), KeyboardButton(text="🏠 В меню")]], resize_keyboard=True)

def main_menu(user_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
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
    await message.answer("Привет! Выбери предмет:", reply_markup=main_menu(message.from_user.id))
    await message.answer("Используй кнопки ниже.", reply_markup=main_reply_keyboard())

@dp.message(F.text == "🔄 Перезапустить")
async def restart_bot(message: types.Message, state: FSMContext):
    await cmd_start(message, state)

@dp.message(F.text == "❌ Отмена")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_menu(message.from_user.id))

@dp.message(F.text == "🏠 В меню")
async def go_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu(message.from_user.id))

# --- СВЯЗЬ С АДМИНОМ (ИСПРАВЛЕНО) ---
@dp.message(F.text == "✉️ Связаться с админом")
async def contact_admin(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Вы админ :)")
        return
    await state.set_state(ContactAdmin.waiting_for_message)
    await message.answer("Напишите сообщение админу (текст или фото).", reply_markup=cancel_keyboard())

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
        else:
            await message.answer("❌ Отправь текст или фото.")
            return

        await message.answer("✅ Отправлено!", reply_markup=main_reply_keyboard())
        await state.clear()
    except Exception as e:
        print(f"Ошибка отправки админу: {e}")
        await message.answer("❌ Ошибка отправки. Возможно, админ заблокировал бота.")
        await state.clear()

@dp.callback_query(F.data.startswith("reply_"))
async def start_reply_to_user(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.data.split("_")[1]
    await state.update_data(reply_user_id=user_id)
    await state.set_state(ReplyToUser.waiting_for_reply)
    await callback.message.answer(f"Ответ для {user_id}:", reply_markup=cancel_keyboard())
    await callback.answer()

@dp.message(ReplyToUser.waiting_for_reply)
async def process_admin_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_user_id')
    try:
        if message.text:
            await bot.send_message(user_id, f"👑 **Ответ от админа:**\n\n{message.text}", parse_mode="Markdown")
        elif message.photo:
            await bot.send_photo(user_id, message.photo[-1].file_id, caption="👑 **Фото от админа**")
        await message.answer("✅ Отправлено!", reply_markup=main_reply_keyboard())
    except Exception:
        await message.answer("❌ Ошибка. Пользователь заблокировал бота.", reply_markup=main_reply_keyboard())
    await state.clear()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    users = get_users()
    subjects = get_subjects()
    lectures = supabase.table('lectures').select('id').execute().data
    total_users = len(users)
    blocked_users = sum(1 for u in users if u[3] == 1)
    text = (f"📊 **Статистика:**\n\n👥 Пользователей: {total_users}\n🚫 Заблокировано: {blocked_users}\n✅ Активных: {total_users - blocked_users}\n\n📚 Предметов: {len(subjects)}\n📝 Лекций: {len(lectures)}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("subj_"))
async def show_dates(callback: types.CallbackQuery):
    subj_id = int(callback.data.split("_")[1])
    dates = get_lectures(subj_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    if not dates:
        await callback.message.edit_text("Нет лекций.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]]))
        return
    for lect_id, date, status in dates:
        prefix = "✅ " if status == "read" else "📅 "
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{prefix}{date}", callback_data=f"lect_{lect_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    await callback.message.edit_text("Выбери лекцию:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("lect_"))
async def show_lecture(callback: types.CallbackQuery):
    lect_id = callback.data.split("_")[1]
    info = get_lecture_info(lect_id)
    if info and info[1]:
        date, photo_ids_str = info
        photo_ids = photo_ids_str.split(',')
        
        status_res = supabase.table('lectures').select('status').eq('id', lect_id).execute()
        status = status_res.data[0]['status']
        
        mark_kb = InlineKeyboardMarkup(inline_keyboard=[])
        if status != "read":
            mark_kb.inline_keyboard.append([InlineKeyboardButton(text="✅ Отметить прочитанным", callback_data=f"markread_{lect_id}")])
        else:
            mark_kb.inline_keyboard.append([InlineKeyboardButton(text="↩️ Снять отметку", callback_data=f"unmarkread_{lect_id}")])
            
        caption = f"Лекция: {date}"
        if len(photo_ids) > 1:
            media_group = [InputMediaPhoto(media=p_id, caption=caption if i==0 else None) for i, p_id in enumerate(photo_ids)]
            await callback.message.answer_media_group(media=media_group)
            await callback.message.answer("Действия:", reply_markup=mark_kb)
        else:
            await callback.message.answer_photo(photo=photo_ids[0], caption=caption, reply_markup=mark_kb)
        await callback.answer()
    else:
        await callback.answer("Ошибка.")

@dp.callback_query(F.data.startswith("markread_"))
async def mark_as_read(callback: types.CallbackQuery):
    lect_id = callback.data.split("_")[1]
    supabase.table('lectures').update({"status": "read"}).eq('id', lect_id).execute()
    await callback.answer("Отлично! Прочитано.")

@dp.callback_query(F.data.startswith("unmarkread_"))
async def unmark_as_read(callback: types.CallbackQuery):
    lect_id = callback.data.split("_")[1]
    supabase.table('lectures').update({"status": "new"}).eq('id', lect_id).execute()
    await callback.answer("Отметка снята.")

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("Выбери предмет:", reply_markup=main_menu(callback.from_user.id))
    await callback.message.answer("Меню", reply_markup=main_reply_keyboard())

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить предмет", callback_data="add_subject"), InlineKeyboardButton(text="✏️ Изменить предмет", callback_data="edit_subject_menu")],
        [InlineKeyboardButton(text="🖼 Добавить лекцию", callback_data="add_lecture"), InlineKeyboardButton(text="✏️ Изменить лекцию", callback_data="edit_lect_menu")],
        [InlineKeyboardButton(text="🗑 Удалить предмет", callback_data="del_subject_menu"), InlineKeyboardButton(text="🗑 Удалить лекцию", callback_data="del_lect_menu")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="view_users"), InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("⚙️ Админ-панель:", reply_markup=keyboard)

@dp.callback_query(F.data == "view_users")
async def view_users(callback: types.CallbackQuery):
    users = get_users()
    if not users:
        await callback.answer("Пусто.", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    text = "👥 **Пользователи:**\n\n"
    for user_id, username, first_name, is_blocked in users:
        status = "🚫" if is_blocked == 1 else "✅"
        user_link = f"@{username}" if username else ""
        text += f"• {first_name} {user_link} {status}\n"
        if user_id != ADMIN_ID:
            btn_text = "🔓 Разблокировать" if is_blocked == 1 else "🚫 Заблокировать"
            keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{btn_text}: {first_name}", callback_data=f"toggleblock_{user_id}")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    await callback.message.edit_text(text[:4000], reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("toggleblock_"))
async def toggle_block(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    res = supabase.table('users').select('is_blocked').eq('user_id', user_id).execute()
    new_status = 0 if res.data[0]['is_blocked'] == 1 else 1
    supabase.table('users').update({"is_blocked": new_status}).eq('user_id', user_id).execute()
    await callback.answer("Статус изменен!")
    await view_users(callback)

# --- ЗАЩИТА ОТ СПАМА ---
@dp.callback_query(AddSubject.waiting_for_name)
async def ignore_callbacks_in_name(callback: types.CallbackQuery):
    await callback.answer("Введи текст или нажми «❌ Отмена».")

@dp.callback_query(AddLecture.waiting_for_date)
async def ignore_callbacks_in_date(callback: types.CallbackQuery):
    await callback.answer("Введи номер/тему или нажми «❌ Отмена».")

# --- ДОБАВЛЕНИЕ ПРЕДМЕТА ---
@dp.callback_query(F.data == "add_subject")
async def start_add_subject(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddSubject.waiting_for_name)
    await callback.message.answer("Введи название предмета:", reply_markup=cancel_keyboard())

@dp.message(AddSubject.waiting_for_name)
async def process_subj_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddSubject.waiting_for_teacher)
    await message.answer("Введи имя преподавателя:", reply_markup=cancel_keyboard())

@dp.message(AddSubject.waiting_for_teacher)
async def process_subj_teacher(message: types.Message, state: FSMContext):
    data = await state.get_data()
    supabase.table('subjects').insert({"name": data['name'], "teacher": message.text}).execute()
    await state.clear()
    await message.answer(f"✅ Предмет '{data['name']}' добавлен!", reply_markup=main_menu(message.from_user.id))
    await message.answer("Выбери действие:", reply_markup=main_reply_keyboard())

# --- ДОБАВЛЕНИЕ ЛЕКЦИИ ---
@dp.callback_query(F.data == "add_lecture")
async def start_add_lecture(callback: types.CallbackQuery, state: FSMContext):
    subjects = get_subjects()
    if not subjects:
        await callback.message.edit_text("Сначала добавь предмет!")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=name, callback_data=f"addlect_{subj_id}")] for subj_id, name in subjects])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_panel")])
    await state.set_state(AddLecture.waiting_for_subject)
    await callback.message.edit_text("К какому предмету добавляем?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("addlect_"))
async def process_lect_subject(callback: types.CallbackQuery, state: FSMContext):
    subj_id = callback.data.split("_")[1]
    await state.update_data(subject_id=subj_id, photos=[])
    await state.set_state(AddLecture.waiting_for_date)
    await callback.message.answer("Введи номер лекции или её тему (например: «Лекция 1» или «Введение»):", reply_markup=cancel_keyboard())

@dp.message(AddLecture.waiting_for_date)
async def process_lect_date(message: types.Message, state: FSMContext):
    await state.update_data(date=message.text)
    await state.set_state(AddLecture.waiting_for_photo)
    await message.answer("Отправь ФОТО, затем нажми «✅ Готово»:", reply_markup=done_keyboard())

@dp.message(AddLecture.waiting_for_photo, F.photo)
async def process_lect_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"📸 Фото №{len(photos)}. Отправь ещё или жми «✅ Готово».", reply_markup=done_keyboard())

@dp.message(AddLecture.waiting_for_photo, F.text == "✅ Готово")
async def finish_lecture_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get('photos', [])
    if not photos:
        await message.answer("Нет фото!", reply_markup=done_keyboard())
        return
    supabase.table('lectures').insert({
        "subject_id": data['subject_id'],
        "date": data['date'],
        "photo_ids": ",".join(photos),
        "status": "new"
    }).execute()
    await state.clear()
    await message.answer(f"✅ Лекция '{data['date']}' сохранена!", reply_markup=main_menu(message.from_user.id))
    await message.answer("Выбери действие:", reply_markup=main_reply_keyboard())

@dp.message(AddLecture.waiting_for_photo)
async def process_lect_wrong(message: types.Message):
    await message.answer("❌ Жду ФОТО или кнопку «✅ Готово».", reply_markup=done_keyboard())

# --- РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ ---
@dp.callback_query(F.data == "edit_subject_menu")
async def edit_subject_menu(callback: types.CallbackQuery):
    subjects = get_subjects()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=name, callback_data=f"editsubj_{subj_id}")] for subj_id, name in subjects])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    await callback.message.edit_text("Что изменить?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("editsubj_"))
async def process_edit_subject(callback: types.CallbackQuery, state: FSMContext):
    subj_id = callback.data.split("_")[1]
    info = get_subject_info(subj_id)
    await state.update_data(subject_id=subj_id)
    await state.set_state(EditSubject.waiting_for_new_name)
    await callback.message.answer(f"Текущее: {info[0]}\nВведи НОВОЕ название:", reply_markup=cancel_keyboard())

@dp.message(EditSubject.waiting_for_new_name)
async def edit_subj_name(message: types.Message, state: FSMContext):
    await state.update_data(new_name=message.text)
    await state.set_state(EditSubject.waiting_for_new_teacher)
    await message.answer("Введи НОВОЕ имя препода:", reply_markup=cancel_keyboard())

@dp.message(EditSubject.waiting_for_new_teacher)
async def edit_subj_teacher(message: types.Message, state: FSMContext):
    data = await state.get_data()
    supabase.table('subjects').update({"name": data['new_name'], "teacher": message.text}).eq('id', data['subject_id']).execute()
    await state.clear()
    await message.answer("✅ Обновлено!", reply_markup=main_menu(message.from_user.id))

@dp.callback_query(F.data == "del_subject_menu")
async def del_subject_menu(callback: types.CallbackQuery):
    subjects = get_subjects()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"❌ {name}", callback_data=f"delsubj_{subj_id}")] for subj_id, name in subjects])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    await callback.message.edit_text("Что удалить?", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("delsubj_"))
async def process_del_subject(callback: types.CallbackQuery):
    subj_id = callback.data.split("_")[1]
    supabase.table('lectures').delete().eq('subject_id', subj_id).execute()
    supabase.table('subjects').delete().eq('id', subj_id).execute()
    await callback.answer("Удалено!", show_alert=True)
    await admin_panel(callback)

@dp.callback_query(F.data == "del_lect_menu")
async def del_lect_menu(callback: types.CallbackQuery):
    subjects = get_subjects()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=name, callback_data=f"del_lect_subj_{subj_id}")] for subj_id, name in subjects])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    await callback.message.edit_text("Предмет:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("del_lect_subj_"))
async def del_lect_choose_date(callback: types.CallbackQuery):
    subj_id = callback.data.split("_")[3]
    lectures = get_lectures(subj_id)
    if not lectures:
        await callback.answer("Нет лекций!", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"❌ {date}", callback_data=f"del_lect_{lect_id}")] for lect_id, date, status in lectures])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="del_lect_menu")])
    await callback.message.edit_text("Удалить лекцию:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("del_lect_") & ~F.data.startswith("del_lect_subj_") & ~F.data.startswith("del_lect_menu"))
async def process_del_lecture(callback: types.CallbackQuery):
    lect_id = callback.data.split("_")[2]
    supabase.table('lectures').delete().eq('id', lect_id).execute()
    await callback.answer("Удалено!", show_alert=True)
    await admin_panel(callback)

# --- ЗАПУСК И БУДИЛЬНИК ---
from aiohttp import web

async def web_server():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is alive!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

async def keep_alive():
    while True:
        await asyncio.sleep(600)
        try:
            async with aiohttp.ClientSession() as session:
                await session.get("https://study-bot-o2vn.onrender.com/") 
        except Exception:
            pass

async def main():
    print("Бот запущен и готов к работе!")
    asyncio.create_task(web_server())
    asyncio.create_task(keep_alive())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
