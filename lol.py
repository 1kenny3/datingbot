import logging
from typing import List, Optional, Tuple
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from database import add_profile, get_profile, add_like, check_mutual_like, get_all_profiles_except, get_user_likes


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
API_TOKEN = '7520048118:AAE_qdahHxliOAGLRYT99NbYpKD8scOT4Wo'
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Состояния FSM
class ProfileStates(StatesGroup):
    name = State()
    age = State()
    description = State()
    photo = State()

# Клавиатуры
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Создать профиль"), KeyboardButton("Смотреть анкеты"))
    return keyboard

def get_like_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("👍 Лайк"), KeyboardButton("👎 Дизлайк"))
    return keyboard

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(
        "Добро пожаловать! Выберите действие:",
        reply_markup=get_main_keyboard()
    )

# Создание профиля
@dp.message_handler(lambda message: message.text == "Создать профиль")
async def create_profile(message: types.Message):
    await ProfileStates.name.set()
    await message.answer("Введите ваше имя:")

@dp.message_handler(state=ProfileStates.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await ProfileStates.next()
    await message.answer("Введите ваш возраст (число):")

@dp.message_handler(lambda message: not message.text.isdigit(), state=ProfileStates.age)
async def process_age_invalid(message: types.Message):
    await message.answer("Возраст должен быть числом. Пожалуйста, введите корректный возраст:")

@dp.message_handler(lambda message: message.text.isdigit(), state=ProfileStates.age)
async def process_age(message: types.Message, state: FSMContext):
    age = int(message.text)
    if age < 18 or age > 100:
        await message.answer("Возраст должен быть от 18 до 100 лет. Введите корректный возраст:")
        return
    await state.update_data(age=age)
    await ProfileStates.next()
    await message.answer("Расскажите о себе:")

@dp.message_handler(state=ProfileStates.description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await ProfileStates.next()
    await message.answer("Отправьте свое фото:")

@dp.message_handler(content_types=['photo'], state=ProfileStates.photo)
async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    
    add_profile(
        message.from_user.id,
        data['name'],
        data['age'],
        data['description'],
        photo_id
    )
    
    await state.finish()
    await message.answer(
        "Профиль успешно создан! Теперь вы можете смотреть анкеты.",
        reply_markup=get_main_keyboard()
    )

# Просмотр анкет
@dp.message_handler(lambda message: message.text == "Смотреть анкеты")
async def start_viewing(message: types.Message):
    user_id = message.from_user.id
    if not get_profile(user_id):
        await message.answer("Сначала создайте свой профиль!")
        return

    profiles = get_all_profiles_except(user_id)
    if not profiles:
        await message.answer("Пока нет доступных анкет для просмотра.")
        return

    state = dp.current_state(user=user_id)
    await state.update_data(profiles=profiles, current_profile_idx=0)
    await send_next_profile(message, user_id)

async def send_next_profile(message: types.Message, user_id: int):
    try:
        state = dp.current_state(user=user_id)
        data = await state.get_data()
        
        profiles = data.get('profiles', [])
        current_profile_idx = data.get('current_profile_idx', 0)
        
        if current_profile_idx >= len(profiles):
            await message.answer(
                "Вы просмотрели все анкеты.",
                reply_markup=get_main_keyboard()
            )
            await state.reset_data()
            return
            
        profile = profiles[current_profile_idx]
        profile_id, name, age, description, photo_id = profile
        
        await state.update_data(
            current_profile_idx=current_profile_idx + 1,
            current_profile_id=profile_id,
            viewing_profile=True
        )
        
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo_id,
            caption=f"Имя: {name}\nВозраст: {age}\nО себе: {description}",
            reply_markup=get_like_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error sending profile: {e}")
        await message.answer(
            "Произошла ошибка при показе анкеты.",
            reply_markup=get_main_keyboard()
        )

# Обработка лайков/дизлайков
@dp.message_handler(lambda message: message.text in ["👍 Лайк", "👎 Дизлайк"])
async def process_like_dislike(message: types.Message):
    user_id = message.from_user.id
    action = message.text
    logger.info(f"User_id {user_id} selected {action}")

    try:
        state = dp.current_state(user=user_id)
        data = await state.get_data()
        logger.info(f"Current state data for user {user_id}: {data}")

        # Проверяем, есть ли входящий лайк
        current_like_from = data.get('current_like_from')
        
        if current_like_from is not None:
            logger.info(f"Processing reply like from {current_like_from}")
            
            if action == "👎 Дизлайк":
                await message.answer(
                    "Анкета пропущена.",
                    reply_markup=get_main_keyboard()
                )
                await state.reset_data()
                return

            # Добавляем ответный лайк
            add_like(user_id, current_like_from)
            
            # Проверяем взаимность
            if check_mutual_like(user_id, current_like_from):
                user_profile = get_profile(user_id)
                liked_user_profile = get_profile(current_like_from)
                
                if user_profile and liked_user_profile:
                    user_contact = f"@{message.from_user.username}" if message.from_user.username else f"ID: {user_id}"
                    try:
                        liked_user = await bot.get_chat(current_like_from)
                        liked_user_contact = f"@{liked_user.username}" if liked_user.username else f"ID: {current_like_from}"
                    except Exception as e:
                        logger.error(f"Error getting liked user chat: {e}")
                        liked_user_contact = f"ID: {current_like_from}"

                    # Отправляем уведомления с фото обоим пользователям
                    name, age, description, photo_id = liked_user_profile
                    await bot.send_photo(
                        user_id,
                        photo=photo_id,
                        caption=f"У вас взаимный лайк с {name} ({age} лет).\n"
                               f"О себе: {description}\n"
                               f"Контакт: {liked_user_contact}",
                        reply_markup=get_main_keyboard()
                    )
                    
                    name, age, description, photo_id = user_profile
                    await bot.send_photo(
                        current_like_from,
                        photo=photo_id,
                        caption=f"У вас взаимный лайк с {name} ({age} лет).\n"
                               f"О себе: {description}\n"
                               f"Контакт: {user_contact}",
                        reply_markup=get_main_keyboard()
                    )
            
            await state.reset_data()
            return

        # Если это обычный лайк при просмотре анкет
        current_profile_id = data.get('current_profile_id')
        viewing_profile = data.get('viewing_profile', False)

        if not viewing_profile or current_profile_id is None:
            # Проверяем, есть ли входящие лайки в базе
            liked_by = get_user_likes(user_id)
            if liked_by:
                # Если есть входящие лайки, обрабатываем последний
                last_like_from = liked_by[-1]
                await state.update_data(current_like_from=last_like_from)
                # Рекурсивно вызываем обработчик
                return await process_like_dislike(message)
            else:
                await message.answer(
                    "Сначала начните просмотр анкет.",
                    reply_markup=get_main_keyboard()
                )
            return

        # Обработка обычного лайка
        logger.info(f"Processing regular like for profile {current_profile_id}")
        
        if action == "👎 Дизлайк":
            await message.answer("Анкета пропущена.")
        else:
            add_like(user_id, current_profile_id)
            # Отправляем уведомление о лайке
            user_profile = get_profile(user_id)
            if user_profile:
                liked_state = dp.current_state(user=current_profile_id)
                await liked_state.set_data({'current_like_from': user_id})
                
                name, age, description, photo_id = user_profile
                await bot.send_photo(
                    current_profile_id,
                    photo=photo_id,
                    caption=f"Ваша анкета получила лайк от {name} ({age} лет).\n"
                           f"О себе: {description}\n\n"
                           "Выберите действие:",
                    reply_markup=get_like_keyboard()
                )

        await send_next_profile(message, user_id)

    except Exception as e:
        logger.error(f"Error processing like/dislike: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при обработке действия.",
            reply_markup=get_main_keyboard()
        )

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)