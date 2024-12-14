import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
import sqlite3

API_TOKEN = 'YOUR_BOT_API_TOKEN'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Создаем базу данных
def create_db():
    conn = sqlite3.connect('dating_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    name TEXT,
                    age INTEGER,
                    description TEXT,
                    photo TEXT,
                    interests TEXT)''')
    conn.commit()
    conn.close()

create_db()

# Состояния анкеты
class UserForm(StatesGroup):
    name = State()  # Ожидаем имя
    age = State()   # Ожидаем возраст
    description = State()  # Ожидаем описание
    photo = State()  # Ожидаем фото
    interests = State()  # Ожидаем интересы

# Начало анкеты
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет! Я помогу тебе создать анкету. Начни с введения имени.")
    await UserForm.name.set()

# Сохраняем имя
@dp.message_handler(state=UserForm.name)
async def get_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text
    conn = sqlite3.connect('dating_bot.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users (user_id, name) VALUES (?, ?)', (user_id, name))
    conn.commit()
    conn.close()
    await message.answer("Имя сохранено! Теперь укажи свой возраст.")
    await UserForm.age.set()

# Сохраняем возраст
@dp.message_handler(lambda message: message.text.isdigit(), state=UserForm.age)
async def get_age(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    age = int(message.text)
    conn = sqlite3.connect('dating_bot.db')
    c = conn.cursor()
    c.execute('UPDATE users SET age = ? WHERE user_id = ?', (age, user_id))
    conn.commit()
    conn.close()
    await message.answer("Возраст сохранен! Теперь расскажи о себе.")
    await UserForm.description.set()

# Сохраняем описание
@dp.message_handler(state=UserForm.description)
async def get_description(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    description = message.text
    conn = sqlite3.connect('dating_bot.db')
    c = conn.cursor()
    c.execute('UPDATE users SET description = ? WHERE user_id = ?', (description, user_id))
    conn.commit()
    conn.close()
    await message.answer("Описание сохранено! Теперь отправь фото профиля.")
    await UserForm.photo.set()

# Загружаем фото
@dp.message_handler(content_types=['photo'], state=UserForm.photo)
async def get_photo(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    conn = sqlite3.connect('dating_bot.db')
    c = conn.cursor()
    c.execute('UPDATE users SET photo = ? WHERE user_id = ?', (photo_id, user_id))
    conn.commit()
    conn.close()
    await message.answer("Фото профиля сохранено! Теперь выбери свои интересы.")
    await UserForm.interests.set()

# Кнопки для выбора интересов
@dp.message_handler(commands=['interests'], state=UserForm.interests)
async def show_interests(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ["IT", "Спорт", "Музыка", "Искусство", "Путешествия", "Кулинария", "Книги", "Фильмы", "Фотография", "Игры"]
    markup.add(*buttons)
    await message.answer("Выбери свои интересы.", reply_markup=markup)

# Сохраняем интересы
@dp.message_handler(lambda message: message.text in ["IT", "Спорт", "Музыка", "Искусство", "Путешествия", "Кулинария", "Книги", "Фильмы", "Фотография", "Игры"], state=UserForm.interests)
async def save_interests(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    interest = message.text
    conn = sqlite3.connect('dating_bot.db')
    c = conn.cursor()
    c.execute('SELECT interests FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result and result[0]:
        new_interests = result[0] + ', ' + interest
    else:
        new_interests = interest
    c.execute('UPDATE users SET interests = ? WHERE user_id = ?', (new_interests, user_id))
    conn.commit()
    conn.close()
    await message.answer(f"Интерес '{interest}' добавлен! Ты завершил создание анкеты.")
    await state.finish()

# Поиск анкет по интересам
@dp.message_handler(commands=['find_by_interest'])
async def find_by_interest(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect('dating_bot.db')
    c = conn.cursor()
    c.execute('SELECT interests FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result and result[0]:
        user_interests = result[0].split(', ')
        c.execute('SELECT * FROM users WHERE interests LIKE ?', ('%' + user_interests[0] + '%',))
        users = c.fetchall()
        if users:
            for user in users:
                await message.answer(f"Имя: {user[1]}, Возраст: {user[2]}, Описание: {user[3]}, Интересы: {user[5]}")
        else:
            await message.answer("Нет анкет по этому интересу.")
    else:
        await message.answer("Ты не выбрал интересы.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
