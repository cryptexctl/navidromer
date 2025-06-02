import os
import hashlib
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.exceptions import BadRequest

API_TOKEN = 'YOUR_BOT_TOKEN'
BASE_MUSIC_PATH = "/path/to/music/"
ALLOWED_CHANNEL_ID = "YOUR_CHANNEL_ID"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

def shorten_callback_data(file_name):
    return hashlib.sha1(file_name.encode()).hexdigest()[:12]

def generate_main_menu():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("📀 Отправить один трек", callback_data="single_track"),
        InlineKeyboardButton("🎼 Отправить несколько треков", callback_data="multiple_tracks")
    )
    return keyboard

def generate_commit_hash(file_name, username):
    commit_string = f"{file_name}_{username}"
    return hashlib.sha1(commit_string.encode()).hexdigest()[:7]

def generate_success_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Вернуться в меню", callback_data="back_to_menu"))
    return keyboard

def generate_confirmation_keyboard(file_id, file_name):
    file_hash = shorten_callback_data(file_name)
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить загрузку", callback_data=f"confirm_{file_hash}"),
        InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{file_hash}")
    )
    return keyboard

pending_files = {}

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("👋 Привет!\nВсе загружаемое тут:@navimus\nВыберите режим загрузки:", reply_markup=generate_main_menu())

@dp.my_chat_member_handler()
async def handle_bot_added_to_channel(event: types.ChatMemberUpdated):
    if event.chat.id != ALLOWED_CHANNEL_ID:
        await bot.leave_chat(event.chat.id)

@dp.callback_query_handler(lambda c: c.data in ["single_track", "multiple_tracks"])
async def process_mode_selection(callback_query: types.CallbackQuery):
    mode = "один трек" if callback_query.data == "single_track" else "несколько треков"
    await bot.answer_callback_query(callback_query.id)
    await bot.edit_message_text("🔄 Режим: {}. Пожалуйста, загрузите файл(ы).".format(mode),
                                chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id)

@dp.message_handler(content_types=types.ContentType.AUDIO)
async def handle_audio(message: types.Message):
    username = message.from_user.username or f"user_{message.from_user.id}"
    title = message.audio.title or "Без названия"
    performer = message.audio.performer or "Неизвестный автор"
    file_name = message.audio.file_name
    file_id = message.audio.file_id

    file_hash = shorten_callback_data(file_name)
    pending_files[file_hash] = {"file_id": file_id, "file_name": file_name, "username": username}

    info_text = f"📜 Информация о треке:\nНазвание: {title}\nАвтор: {performer}\n\nЗагрузить трек?"
    await message.reply(info_text, reply_markup=generate_confirmation_keyboard(file_id, file_name))

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_"))
async def confirm_upload(callback_query: types.CallbackQuery):
    try:
        file_hash = callback_query.data.split("_", 1)[1]
        file_info = pending_files.get(file_hash)
        if not file_info:
            await bot.answer_callback_query(callback_query.id, text="⚠️ Данные о файле не найдены.")
            return

        file_id = file_info["file_id"]
        file_name = file_info["file_name"]
        username = file_info["username"]
        user_dir = os.path.join(BASE_MUSIC_PATH, username)
        os.makedirs(user_dir, exist_ok=True)

        file_details = await bot.get_file(file_id)
        file_path = os.path.join(user_dir, file_name)
        await bot.download_file(file_details.file_path, file_path)

        commit_hash = generate_commit_hash(file_name, username)
        commit_message = f"{commit_hash} @{username} Добавлено {file_name}"
        await bot.send_message(ALLOWED_CHANNEL_ID, commit_message)

        await bot.edit_message_text("✅ Трек успешно загружен!", chat_id=callback_query.from_user.id,
                                    message_id=callback_query.message.message_id,
                                    reply_markup=generate_success_keyboard())
        pending_files.pop(file_hash, None)

    except BadRequest as e:
        await bot.answer_callback_query(callback_query.id, text=f"⚠️ Ошибка: {e}")

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_"))
async def cancel_upload(callback_query: types.CallbackQuery):
    file_hash = callback_query.data.split("_", 1)[1]
    file_info = pending_files.pop(file_hash, None)
    if file_info:
        await bot.edit_message_text(f"❌ Загрузка {file_info['file_name']} отменена.",
                                    chat_id=callback_query.from_user.id,
                                    message_id=callback_query.message.message_id,
                                    reply_markup=generate_main_menu())
    else:
        await bot.answer_callback_query(callback_query.id, text="⚠️ Файл не найден.")

@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback_query: types.CallbackQuery):
    await bot.edit_message_text("👋 Привет!\nВсе загружаемое тут:@navimus\nВыберите режим загрузки:",
                                chat_id=callback_query.from_user.id,
                                message_id=callback_query.message.message_id,
                                reply_markup=generate_main_menu())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
 
