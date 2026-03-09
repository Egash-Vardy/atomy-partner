import asyncio
import sqlite3
import logging
import os
from aiohttp import web  # Добавили для веб-сервера
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- НАСТРОЙКИ ---
API_TOKEN = '8779350094:AAFcX0HzlK_8FOmFEJAjH31gQimf7LF6378'
ADMIN_IDS = [8065108309, 1613877823, 8779350094, 6484236894]
DB_NAME = "community_pro.db"
CHANNEL_URL = "https://t.me/workAtomy"
CHANNEL_ID = "@workAtomy"
CHECKLIST_URL = "https://clipr.cc/RC4rz"
ADMIN_CONTACT = "https://clipr.cc/HWHb0"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

# --- Веб-сервер для Render (обманка) ---
async def handle(request):
    return web.Response(text="Бот работает!")

# --- СТАТУСЫ ---
class UserSteps(StatesGroup):
    waiting_for_start = State()
    waiting_for_experience = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()

def update_user_step(user_id, step):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET step = ? WHERE user_id = ?", (step, user_id))
    conn.commit()
    conn.close()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users 
                   (user_id INTEGER PRIMARY KEY, name TEXT, username TEXT, 
                    reg_date TEXT, step TEXT DEFAULT 'start')""")
    conn.commit()
    conn.close()

async def check_is_subscribed(user_id: int):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

async def send_reminder(user_id: int, name: str):
    if await check_is_subscribed(user_id):
        return
    try:
        text = (f"Привет, {name}!\n\n"
                f"Ты ещё не присоединился к <a href='{CHANNEL_URL}'>нашему основному каналу</a>? "
                f"Там ресурсы и новости бизнеса Atomy.\n\n"
                f"<a href='{CHANNEL_URL}'>Присоединяйся прямо сейчас!</a>")
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Ошибка напоминания: {e}")

# --- ПРИВЕТСТВИЕ ---
@dp.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    uid, name = m.from_user.id, m.from_user.first_name
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, name, username, reg_date) VALUES (?, ?, ?, ?)",
                (uid, name, m.from_user.username, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    update_user_step(uid, "started")
    buttons = [[KeyboardButton(text="Да, я готова!")]]
    if uid in ADMIN_IDS:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    text = (f"Привет, {name}!👋\n"
            f"Рада приветствовать тебя в нашем бизнес-канале по Atomy!🌟 Я помогу тебе начать и "
            f"познакомлю с партнёрской программой. Ты готова начать? Напиши «Да» или нажми на кнопку!")
    await m.answer(text, reply_markup=kb)
    await state.set_state(UserSteps.waiting_for_start)
    scheduler.add_job(send_reminder, 'date', run_date=datetime.now() + timedelta(days=1), args=[uid, name])

# --- СБОР ДАННЫХ ---
@dp.message(UserSteps.waiting_for_start, F.text.contains("Да"))
async def ask_experience(m: types.Message, state: FSMContext):
    name = m.from_user.first_name
    update_user_step(m.from_user.id, "clicked_yes")
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Новичок"), KeyboardButton(text="Опытный")],
        [KeyboardButton(text="Расскажи больше")]
    ], resize_keyboard=True)
    await m.answer(f"Супер, {name}!🙌 Сколько времени ты уже занимаешься сетевым маркетингом?", reply_markup=kb)
    await state.set_state(UserSteps.waiting_for_experience)

# --- ВЫДАЧА ЧЕК-ЛИСТА ---
@dp.message(UserSteps.waiting_for_experience)
async def give_checklist(m: types.Message, state: FSMContext):
    name = m.from_user.first_name
    update_user_step(m.from_user.id, "received_checklist")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Перейти в основной канал", url=CHANNEL_URL)]
    ])
    text_main = (f"Отлично, {name}!💪\n\n"
                 f"Вот твой чек-лист для старта в Atomy: <a href='{CHECKLIST_URL}'>ОТКРЫТЬ ЧЕК-ЛИСТ</a>\n"
                 f"В нем ты найдешь:\n"
                 f"• Шаг 1: Запуск личного бренда\n"
                 f"• Шаг 2: Понедельный гайд для старта\n"
                 f"• Шаг 3: Главные ошибки новичка\n"
                 f"• Шаг 4: Узнаешь какой доход можно получать\n\n"
                 f"Ты на правильном пути, {name}! Не забывай, что у тебя есть поддержка. "
                 f"Если застряла — <a href='{ADMIN_CONTACT}'>пиши мне</a>\n\n"
                 f"<b>Присоединяйся к нашему основному каналу ✅ и развивай свой бизнес с Atomy!🤩 Советы, обучение и реальный опыт – всё в одном месте!❤️</b>")
    await m.answer(text_main, parse_mode="HTML", reply_markup=kb)
    await state.clear()

# --- АДМИН ПАНЕЛЬ ---
@dp.message(lambda m: m.from_user.id in ADMIN_IDS and (m.text == "⚙️ Админ-панель" or m.text == "/admin"))
async def admin_menu(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="📢 Рассылка всем", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📥 Скачать базу (DB)", callback_data="adm_download")]
    ])
    await m.answer("⚙️ Меню администратора:", reply_markup=kb)

@dp.callback_query(F.data == "adm_stats")
async def adm_stats(c: types.CallbackQuery):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT step, COUNT(*) FROM users GROUP BY step")
    stats = cur.fetchall()
    conn.close()
    res = "📊 <b>Статистика:</b>\n\n" + "\n".join([f"• {s}: {cnt} чел." for s, cnt in stats])
    await c.message.answer(res, parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data == "adm_broadcast")
async def adm_br_start(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Введите текст рассылки (HTML разрешен):")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await c.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def adm_br_exec(m: types.Message, state: FSMContext):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    conn.close()
    success = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, m.text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await m.answer(f"✅ Доставлено: {success}")
    await state.clear()

@dp.callback_query(F.data == "adm_download")
async def adm_db_get(c: types.CallbackQuery):
    await c.message.answer_document(FSInputFile(DB_NAME))
    await c.answer()

# --- ЗАПУСК ---
async def main():
    # Запуск веб-сервера для Render
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 8080)))
    await site.start()
    
    init_db()
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Бот остановлен!")
