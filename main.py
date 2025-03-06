import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Optional
import os
from dotenv import load_dotenv
from profile_editor import register_handlers


from database import (
    get_profile, add_profile, get_matching_profiles, add_like,
    get_user_interests, add_user_interests, get_all_interests,
    add_viewed_profile, check_mutual_like, add_report, add_block,
    get_recent_likes, update_last_active, clear_user_interests,
    update_username, get_all_users, get_users_by_interests
)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("Не установлен токен бота. Проверьте файл .env")

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Состояния FSM
class ProfileStates(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    description = State()
    photo = State()
    interests = State()
    broadcast_message = State()
    broadcast_interests = State()

# Клавиатуры
def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    profile = get_profile(user_id)
    
    if profile:
        keyboard.add(KeyboardButton("👀 Смотреть анкеты"))
        keyboard.add(KeyboardButton("👤 Мой профиль"))  # Добавляем новую кнопку
        
        recent_likes = get_recent_likes(user_id)
        if recent_likes:
            keyboard.add(KeyboardButton("👀 Посмотреть кто лайкнул"))
            
        keyboard.add(KeyboardButton("📝 Редактировать профиль"))
        keyboard.add(KeyboardButton("📢 Рассылка"))  # Добавляем кнопку рассылки
    else:
        keyboard.add(KeyboardButton("📝 Создать профиль"))
    
    return keyboard

def get_like_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(
        KeyboardButton("👎 Дизлайк"),
        KeyboardButton("❤️ Лайк")
    )
    keyboard.add(KeyboardButton("⚠️ Пожаловаться"))
    keyboard.add(KeyboardButton("🏠 В главное меню"))
    return keyboard

def get_gender_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("👨 Мужской"), KeyboardButton("👩 Женский"))
    return keyboard

def get_looking_for_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        KeyboardButton("👨 Мужчин"),
        KeyboardButton("👩 Женщин"),
        KeyboardButton("👥 Всех")
    )
    return keyboard

def get_interests_keyboard(selected_interests: List[int] = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру с интересами"""
    if selected_interests is None:
        selected_interests = []
        
    keyboard = InlineKeyboardMarkup(row_width=2)
    interests = get_all_interests()
    
    buttons = []
    for interest_id, interest_name in interests:
        mark = "✅ " if interest_id in selected_interests else ""
        buttons.append(
            InlineKeyboardButton(
                text=f"{mark}{interest_name}",
                callback_data=f"interest_{interest_id}"
            )
        )
    
    # Добавляем кнопки по две в ряд
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        keyboard.row(*row)
    
    # Добавляем кнопку "Готово" отдельной строкой
    keyboard.row(InlineKeyboardButton(
        text="Готово ✅",
        callback_data="interests_done"
    ))
    
    return keyboard

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    if username:
        update_username(user_id, username)
    profile = get_profile(user_id)
    
    if profile:
        # Получаем интересы пользователя
        user_interests = get_user_interests(user_id)
        interests_text = ", ".join(user_interests) if user_interests else "Не указаны"
        
        # Маппинг для отображения пола
        gender_map = {"M": "Мужской", "F": "Женский"}
        looking_for_map = {
            "M": "Мужчин",
            "F": "Женщин",
            "MF": "Всех"
        }
        
        # Формируем текст профиля
        profile_text = (
            f"👤 Ваш профиль:\n\n"
            f"Имя: {profile[1]}\n"
            f"Возраст: {profile[2]}\n"
            f"Пол: {gender_map.get(profile[5], 'Не указан')}\n"
            f"Ищу: {looking_for_map.get(profile[6], 'Не указано')}\n"
            f"Город: {profile[7] if profile[7] else 'Не указан'}\n"
            f"О себе: {profile[3]}\n\n"
            f"Интересы: {interests_text}\n\n"
        )
        
        try:
            # Отправляем фото с подписью
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=profile[4],  # photo_id
                caption=profile_text,
                reply_markup=get_main_keyboard(user_id)
            )
        except Exception as e:
            logger.error(f"Error sending profile photo: {e}")
            await message.answer(
                f"❌ Фото недоступно\n\n{profile_text}",
                reply_markup=get_main_keyboard(user_id)
            )
    else:
        await message.answer(
            "Добро пожаловать! Для начала создайте свой профиль:",
            reply_markup=get_main_keyboard(user_id)
        )

# Создание профиля
@dp.message_handler(lambda message: message.text == "📝 Создать профиль")
async def create_profile(message: types.Message):
    await ProfileStates.name.set()
    await message.answer(
        "Введите ваше имя:",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message_handler(state=ProfileStates.name)
async def process_name(message: types.Message, state: FSMContext):
    if len(message.text) < 2:
        await message.answer("Имя должно содержать хотя бы 2 символа. Попробуйте еще раз:")
        return
    
    await state.update_data(name=message.text)
    await ProfileStates.age.set()
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
    await ProfileStates.gender.set()
    await message.answer(
        "Укажите ваш пол:",
        reply_markup=get_gender_keyboard()
    )

# ... продолжение следует ...
@dp.message_handler(state=ProfileStates.gender)
async def process_gender(message: types.Message, state: FSMContext):
    gender_map = {
        "👨 Мужской": "M",
        "👩 Женский": "F"
    }
    
    if message.text not in gender_map:
        await message.answer("Пожалуйста, выберите пол, используя кнопки.")
        return
    
    await state.update_data(gender=gender_map[message.text])
    await ProfileStates.looking_for.set()
    await message.answer(
        "Кого вы хотите найти?",
        reply_markup=get_looking_for_keyboard()
    )

@dp.message_handler(state=ProfileStates.looking_for)
async def process_looking_for(message: types.Message, state: FSMContext):
    looking_for_map = {
        "👨 Мужчин": "M",
        "👩 Женщин": "F",
        "👥 Всех": "MF"
    }
    
    if message.text not in looking_for_map:
        await message.answer("Пожалуйста, выберите предпочтение, используя кнопки.")
        return
    
    await state.update_data(looking_for=looking_for_map[message.text])
    await ProfileStates.city.set()
    await message.answer(
        "Укажите ваш город (или пропустите, отправив '-'):",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message_handler(state=ProfileStates.city)
async def process_city(message: types.Message, state: FSMContext):
    city = None if message.text == '-' else message.text
    await state.update_data(city=city)
    await ProfileStates.description.set()
    await message.answer("Расскажите о себе:")

@dp.message_handler(state=ProfileStates.description)
async def process_description(message: types.Message, state: FSMContext):
    if len(message.text) < 10:
        await message.answer("Описание должно содержать хотя бы 10 символов. Попробуйте еще раз:")
        return
    
    await state.update_data(description=message.text)
    await ProfileStates.photo.set()
    await message.answer("Отправьте свое фото:")

@dp.message_handler(content_types=['photo'], state=ProfileStates.photo)
async def process_photo(message: types.Message, state: FSMContext):
    try:
        photo = message.photo[-1]
        photo_id = photo.file_id
        username = message.from_user.username  # Получаем username пользователя
        
        try:
            await bot.get_file(photo_id)
        except Exception as e:
            logger.error(f"Invalid photo_id: {e}")
            await message.answer("Ошибка при обработке фото. Пожалуйста, отправьте другое фото.")
            return
        
        # Сохраняем фото и username в состояние
        await state.update_data({
            'photo_id': photo_id,
            'username': username
        })
        
        await ProfileStates.interests.set()
        
        # Показываем клавиатуру с интересами
        interests = get_all_interests()
        if not interests:
            logger.error("No interests found in database")
            await message.answer(
                "Произошла ошибка при загрузке интересов. Пожалуйста, попробуйте позже.",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
            return
            
        await message.answer(
            "Выберите ваши интересы (можно выбрать до 5):",
            reply_markup=get_interests_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при обработке фото. Пожалуйста, попробуйте еще раз.",
            reply_markup=ReplyKeyboardRemove()
        )
        # Возвращаемся к этапу фото
        await ProfileStates.photo.set()

@dp.callback_query_handler(lambda c: c.data.startswith('interest_'), state='*')
async def process_interest_selection(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await callback_query.answer()
        
        interest_id = int(callback_query.data.split('_')[1])
        data = await state.get_data()
        
        selected_interests = data.get('selected_interests', [])
        if interest_id in selected_interests:
            selected_interests.remove(interest_id)
        else:
            if len(selected_interests) >= 5:
                await callback_query.answer("Можно выбрать максимум 5 интересов!", show_alert=True)
                return
            selected_interests.append(interest_id)
        
        await state.update_data(selected_interests=selected_interests)
        
        interests = get_all_interests()
        selected_names = [name for id_, name in interests if id_ in selected_interests]
        
        text = "Выберите ваши интересы (можно выбрать до 5):\n\n"
        if selected_names:
            text += f"Выбрано: {', '.join(selected_names)}"
        else:
            text += "Пока ничего не выбрано"
            
        await callback_query.message.edit_text(
            text=text,
            reply_markup=get_interests_keyboard(selected_interests)
        )
        
    except Exception as e:
        logger.error(f"Error in process_interest_selection: {e}", exc_info=True)
        await callback_query.message.answer("Произошла ошибка при выборе интересов")

@dp.callback_query_handler(lambda c: c.data == 'interests_done', state=ProfileStates.interests)
async def process_interests_done(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        selected_interests = data.get('selected_interests', [])
        
        if not selected_interests:
            await callback_query.answer("Выберите хотя бы один интерес!")
            return
        
        user_id = callback_query.from_user.id
        
        # Сохраняем профиль с username
        add_profile(
            user_id=user_id,
            name=data['name'],
            age=data['age'],
            description=data['description'],
            photo_id=data['photo_id'],
            gender=data['gender'],
            looking_for=data['looking_for'],
            city=data.get('city'),
            username=data.get('username')
        )
        
        # Сохраняем интересы
        clear_user_interests(user_id)
        add_user_interests(user_id, selected_interests)
        
        await state.finish()
        await callback_query.message.answer(
            "Профиль успешно создан! Теперь вы можете смотреть анкеты.",
            reply_markup=get_main_keyboard(user_id)
        )
        
    except Exception as e:
        logger.error(f"Error in process_interests_done: {e}", exc_info=True)
        await callback_query.message.answer(
            "Произошла ошибка при создании профиля",
            reply_markup=get_main_keyboard(callback_query.from_user.id)
        )

# ... продолжение следует ...

# Просмотр анкет
@dp.message_handler(lambda message: message.text == "👀 Смотреть анкеты")
async def start_viewing_profiles(message: types.Message):
    try:
        user_id = message.from_user.id
        
        # Получаем профиль пользователя
        user_profile = get_profile(user_id)
        if not user_profile:
            await message.answer(
                "Сначала создайте свой профиль.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
            
        # Получаем подходящие анкеты
        profiles = get_matching_profiles(
            user_id=user_id,
            gender=user_profile[5],  # gender
            looking_for=user_profile[6],  # looking_for
            exclude_viewed=True
        )
        
        logger.info(f"Found profiles for user {user_id}: {len(profiles)}")
        
        if not profiles:
            await message.answer(
                "Пока нет подходящих анкет. Попробуйте позже.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
            
        # Сохраняем список анкет в состоянии
        state = dp.current_state(user=user_id)
        await state.update_data(
            profiles=profiles,
            current_profile_idx=0,
            viewing_profiles=True
        )
        
        # Показываем первую анкету
        await send_next_profile(message, user_id)
        
    except Exception as e:
        logger.error(f"Error starting profile viewing: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при поиске анкет.",
            reply_markup=get_main_keyboard(user_id)
        )

async def send_next_profile(message: types.Message, user_id: int):
    try:
        state = dp.current_state(user=user_id)
        data = await state.get_data()
        
        profiles = data.get('profiles', [])
        current_profile_idx = data.get('current_profile_idx', 0)
        
        if not profiles or current_profile_idx >= len(profiles):
            await message.answer(
                "Вы просмотрели все анкеты. Попробуйте позже.",
                reply_markup=get_main_keyboard(user_id)
            )
            await state.reset_data()
            return
            
        profile = profiles[current_profile_idx]
        profile_id, name, age, description, photo_id, common_interests, age_diff = profile
        
        # Отмечаем профиль как просмотренный
        add_viewed_profile(user_id, profile_id)
        
        # Получаем интересы пользователя
        user_interests = get_user_interests(profile_id)
        interests_text = ", ".join(user_interests) if user_interests else "Не указаны"
        
        caption = (
            f"Имя: {name}\n"
            f"Возраст: {age}\n"
            f"О себе: {description}\n"
            f"Интересы: {interests_text}"
        )
        
        try:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=photo_id,
                caption=caption,
                reply_markup=get_like_keyboard()
            )
        except Exception as photo_error:
            logger.error(f"Error sending photo: {photo_error}")
            await message.answer(
                f"❌ Фото недоступно\n\n{caption}",
                reply_markup=get_like_keyboard()
            )
        
        # Обновляем индекс текущего профиля
        await state.update_data(current_profile_idx=current_profile_idx + 1)
        
    except Exception as e:
        logger.error(f"Error sending profile: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при показе анкеты.",
            reply_markup=get_main_keyboard(user_id)
        )

# Обработка лайков/дизлайков
@dp.message_handler(lambda message: message.text in ["❤️ Лайк", "👎 Дизлайк"])
async def process_reaction(message: types.Message):
    try:
        user_id = message.from_user.id
        state = dp.current_state(user=user_id)
        data = await state.get_data()
        
        if not data.get('viewing_profiles'):
            return
            
        profiles = data.get('profiles', [])
        current_profile_idx = data.get('current_profile_idx', 0)
        
        if current_profile_idx <= 0:
            return
            
        liked_profile = profiles[current_profile_idx - 1]
        liked_user_id = liked_profile[0]
        
        if message.text == "❤️ Лайк":
            add_like(user_id, liked_user_id)
            
            # Получаем информацию о лайкнувшем пользователе
            liker_profile = get_profile(user_id)
            if liker_profile:
                try:
                    # Отправляем уведомление о лайке
                    liker_name = liker_profile[1]  # Имя лайкнувшего
                    notification_text = f"🔔 Вас лайкнул(а) {liker_name}!\nПосмотрите, кто вас лайкнул, нажав на кнопку '👀 Посмотреть кто лайкнул'"
                    
                    await bot.send_message(
                        chat_id=liked_user_id,
                        text=notification_text,
                        reply_markup=get_main_keyboard(liked_user_id)
                    )
                    logger.info(f"Like notification sent from {user_id} to {liked_user_id}")
                except Exception as e:
                    logger.error(f"Error sending like notification: {e}")
            
            # Проверяем взаимный лайк
            if check_mutual_like(user_id, liked_user_id):
                # Получаем информацию о профиле
                matched_profile = get_profile(liked_user_id)
                if matched_profile:
                    matched_name = matched_profile[1]
                    
                    # Отправляем уведомление о взаимной симпатии обоим пользователям
                    match_text = f"💕 У вас взаимная симпатия с {matched_name}!"
                    
                    await message.answer(
                        match_text,
                        reply_markup=get_main_keyboard(user_id)
                    )
                    
                    await bot.send_message(
                        chat_id=liked_user_id,
                        text=f"💕 У вас взаимная симпатия с {liker_profile[1]}!",
                        reply_markup=get_main_keyboard(liked_user_id)
                    )
        
        # Показываем следующую анкету
        await send_next_profile(message, user_id)
        
    except Exception as e:
        logger.error(f"Error processing reaction: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при обработке реакции.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

# Просмотр лайков
@dp.message_handler(lambda message: message.text == "👀 Посмотреть кто лайкнул")
async def show_who_liked(message: types.Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        
        # Получаем последние лайки
        recent_likes = get_recent_likes(user_id)
        logger.info(f"Retrieved likes for user {user_id}: {len(recent_likes)}")
        
        if not recent_likes:
            await message.answer(
                "У вас пока нет новых лайков.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
            
        # Берем самый последний лайк
        liked_from_id, name, age, description, photo_id, timestamp = recent_likes[0]
        
        # Получаем профиль лайкнувшего пользователя
        liker_profile = get_profile(liked_from_id)
        username = liker_profile[8] if liker_profile and len(liker_profile) > 8 else "нет_username"
        
        # Сохраняем ID пользователя для возможного ответного лайка
        await state.update_data(current_profile_id=liked_from_id)
        
        # Создаем клавиатуру для отвтного действия
        response_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        response_keyboard.row(
            KeyboardButton("👎 Пропустить"),
            KeyboardButton("❤️ Лайкнуть в ответ")
        )
        response_keyboard.add(KeyboardButton("🏠 В главное меню"))
        
        caption = (
            f"Вас лайкнул(а):\n\n"
            f"Имя: {name}\n"
            f"Возраст: {age}\n"
            f"О себе: {description}\n"
        )
        
        try:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=photo_id,
                caption=caption,
                reply_markup=response_keyboard
            )
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            await message.answer(
                f"❌ Фото недоступно\n\n{caption}",
                reply_markup=response_keyboard
            )
            
    except Exception as e:
        logger.error(f"Error in show_who_liked: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при показе профиля.",
            reply_markup=get_main_keyboard(user_id)
        )

# Обработка жалоб
@dp.message_handler(lambda message: message.text == "⚠️ Пожаловаться")
async def handle_report(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        current_profile_idx = data.get('current_profile_idx', 0)
        profiles = data.get('profiles', [])
        
        if not profiles or current_profile_idx <= 0:
            await message.answer("Нет активного профиля для жалобы.")
            return
            
        reported_user_id = profiles[current_profile_idx - 1][0]
        add_report(message.from_user.id, reported_user_id)
        add_block(message.from_user.id, reported_user_id)
        
        await message.answer(
            "Жалоба отправлена. Пользователь заблокирован.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
        
    except Exception as e:
        logger.error(f"Error handling report: {e}", exc_info=True)
        await message.answer("Произошла ошибка при отправке жалобы.")

# Возврат в главное меню
@dp.message_handler(lambda message: message.text == "🏠 В главное меню")
async def return_to_main_menu(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        "Вы вернулись в главное меню.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


@dp.message_handler(lambda message: message.text == "❤️ Лайкнуть в ответ")
async def process_return_like(message: types.Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        data = await state.get_data()
        profile_to_like = data.get('current_profile_id')
        
        if not profile_to_like:
            await message.answer(
                "Не удалось найти профиль для лайка.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
            
        add_like(user_id, profile_to_like)
        logger.info(f"Return like added from {user_id} to {profile_to_like}")
        
        if check_mutual_like(user_id, profile_to_like):
            matched_profile = get_profile(profile_to_like)
            user_profile = get_profile(user_id)
            
            if matched_profile and user_profile:
                matched_name = matched_profile[1]
                user_name = user_profile[1]
                
                # Получаем username и формируем контактную информацию
                matched_username = matched_profile[8]
                contact_info = ""
                if matched_username:
                    contact_info = f"\n\nНаписать в личные сообщения: @{matched_username}\nили перейти по ссылке: https://t.me/{matched_username}"
                
                match_text = f"💕 У вас взаимная симпатия с {matched_name}!{contact_info}"
                
                # То же самое для второго пользователя
                user_username = user_profile[8]
                other_contact_info = ""
                if user_username:
                    other_contact_info = f"\n\nНаписать в личные сообщения: @{user_username}\nили перейти по ссылке: https://t.me/{user_username}"
                
                other_match_text = f"💕 У вас взаимная симпатия с {user_name}!{other_contact_info}"
                
                await message.answer(
                    match_text,
                    reply_markup=get_main_keyboard(user_id),
                    disable_web_page_preview=True
                )
                
                await bot.send_message(
                    chat_id=profile_to_like,
                    text=other_match_text,
                    reply_markup=get_main_keyboard(profile_to_like),
                    disable_web_page_preview=True
                )
        else:
            await message.answer(
                "Лайк отправлен! ❤️",
                reply_markup=get_main_keyboard(user_id)
            )
        
        await state.finish()
        
    except Exception as e:
        logger.error(f"Error processing return like: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при отправке лайка.",
            reply_markup=get_main_keyboard(user_id)
        )

# Добавим также обработчик для пропуска
@dp.message_handler(lambda message: message.text == "👎 Пропустить")
async def skip_profile(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        "Профиль пропущен.",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


@dp.message_handler(lambda message: message.text == "👤 Мой профиль")
async def show_my_profile(message: types.Message):
    try:
        user_id = message.from_user.id
        profile = get_profile(user_id)
        
        if not profile:
            await message.answer(
                "У вас еще нет профиля. Создайте его!",
                reply_markup=get_main_keyboard(user_id)
            )
            return
            
        # Получаем интересы пользователя
        user_interests = get_user_interests(user_id)
        interests_text = ", ".join(user_interests) if user_interests else "Не указаны"
        
        # Маппинг для отображения пола
        gender_map = {"M": "Мужской", "F": "Женский"}
        looking_for_map = {
            "M": "Мужчин",
            "F": "Женщин",
            "MF": "Всех"
        }
        
        # Формируем текст профиля
        profile_text = (
            f"👤 Ваш профиль:\n\n"
            f"Имя: {profile[1]}\n"
            f"Возраст: {profile[2]}\n"
            f"Пол: {gender_map.get(profile[5], 'Не указан')}\n"
            f"Ищу: {looking_for_map.get(profile[6], 'Не указано')}\n"
            f"Город: {profile[7] if profile[7] else 'Не указан'}\n"
            f"О себе: {profile[3]}\n\n"
            f"Интересы: {interests_text}\n\n"
        )
        
        try:
            # Отправляем фото с подписью
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=profile[4],  # photo_id
                caption=profile_text,
                reply_markup=get_main_keyboard(user_id)
            )
        except Exception as e:
            logger.error(f"Error sending profile photo: {e}")
            await message.answer(
                f"❌ Фото недоступно\n\n{profile_text}",
                reply_markup=get_main_keyboard(user_id)
            )
            
    except Exception as e:
        logger.error(f"Error showing profile: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при отображении профиля.",
            reply_markup=get_main_keyboard(user_id)
        )

@dp.message_handler(lambda message: message.text == "📢 Рассылка")
async def start_broadcast(message: types.Message):
    await message.answer(
        "Введите текст сообщения для рассылки:",
        reply_markup=ReplyKeyboardRemove()
    )
    await ProfileStates.broadcast_message.set()

@dp.message_handler(state=ProfileStates.broadcast_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    await state.update_data(broadcast_message=message.text)
    await message.answer(
        "Выберите интересы, которым будет отправлено сообщение:",
        reply_markup=get_interests_keyboard()
    )
    await ProfileStates.broadcast_interests.set()

@dp.callback_query_handler(lambda c: c.data.startswith('interest_'), state=ProfileStates.broadcast_interests)
async def process_broadcast_interest_selection(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await callback_query.answer()
        
        interest_id = int(callback_query.data.split('_')[1])
        data = await state.get_data()
        
        selected_interests = data.get('selected_interests', [])
        if interest_id in selected_interests:
            selected_interests.remove(interest_id)
        else:
            selected_interests.append(interest_id)
        
        await state.update_data(selected_interests=selected_interests)
        
        interests = get_all_interests()
        selected_names = [name for id_, name in interests if id_ in selected_interests]
        
        text = "Выберите интересы, которым будет отправлено сообщение:\n\n"
        if selected_names:
            text += f"Выбрано: {', '.join(selected_names)}"
        else:
            text += "Пока ничего не выбрано"
            
        await callback_query.message.edit_text(
            text=text,
            reply_markup=get_interests_keyboard(selected_interests)
        )
        
    except Exception as e:
        logger.error(f"Error in process_broadcast_interest_selection: {e}", exc_info=True)
        await callback_query.message.answer("Произошла ошибка при выборе интересов")

@dp.callback_query_handler(lambda c: c.data == 'interests_done', state=ProfileStates.broadcast_interests)
async def process_broadcast_interests_done(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        selected_interests = data.get('selected_interests', [])
        
        if not selected_interests:
            await callback_query.answer("Выберите хотя бы один интерес!")
            return
        
        await state.update_data(selected_interests=selected_interests)
        
        ADMIN_ID = int(os.getenv('ADMIN_ID').split()[0])  # Загружаем ID администратора из переменных окружения
        admin_id = ADMIN_ID  # Используем загруженный ID администратора
        
        await bot.send_message(
            chat_id=admin_id,
            text=f"Сообщение от {callback_query.from_user.username}:\n{data['broadcast_message']}\n\nВыбранные интересы: {', '.join([name for id_, name in get_all_interests() if id_ in selected_interests])}",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_broadcast"),
                InlineKeyboardButton("❌ Отклонить", callback_data="decline_broadcast")
            )
        )
        await callback_query.message.answer("Ваше сообщение отправлено администратору.")
        await state.finish()
        
    except Exception as e:
        logger.error(f"Error in process_broadcast_interests_done: {e}", exc_info=True)
        await callback_query.message.answer(
            "Произошла ошибка при отправке сообщения администратору.",
            reply_markup=get_main_keyboard(callback_query.from_user.id)
        )

@dp.callback_query_handler(lambda c: c.data == 'confirm_broadcast')
async def confirm_broadcast(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    logger.info(f"Confirm broadcast button pressed by {callback_query.from_user.username}")
    
    try:
        # Получаем текст сообщения и выбранные интересы из callback_query.message.text
        if not callback_query.message.text:
            await callback_query.answer("Ошибка: данные сообщения отсутствуют.")
            return
        
        message_text = callback_query.message.text.split('\n\n')[0].split(':', 1)[1].strip()
        selected_interests_text = callback_query.message.text.split('\n\n')[1].split(': ')[1]
        
        logger.info(f"Message text: {message_text}")
        logger.info(f"Selected interests: {selected_interests_text}")
        
        # Получаем ID выбранных интересов
        all_interests = get_all_interests()
        selected_interests = [id_ for id_, name in all_interests if name in selected_interests_text.split(', ')]
        
        logger.info(f"Selected interest IDs: {selected_interests}")
        
        # Получаем всех пользователей, у которых есть выбранные интересы
        users_with_interests = get_users_by_interests(selected_interests)
        
        logger.info(f"Users with selected interests: {users_with_interests}")
        
        if not users_with_interests:
            await callback_query.message.answer("Нет пользователей с выбранными интересами.")
            return
        
        username = callback_query.message.text.split(':')[0].split(' ')[-1]  # Получаем username отправителя
        for user_id in users_with_interests:
            try:
                await bot.send_message(user_id, f"{message_text}\nНаписать в личные сообщения: @{username}")
                logger.info(f"Message sent to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
        
        await callback_query.message.answer("Рассылка успешно отправлена!")
        await state.finish()
        
    except Exception as e:
        logger.error(f"Error in confirm_broadcast: {e}", exc_info=True)
        await callback_query.message.answer("Произошла ошибка при отправке рассылки.")

@dp.callback_query_handler(lambda c: c.data == 'decline_broadcast')
async def decline_broadcast(callback_query: types.CallbackQuery):
    await callback_query.answer()
    await callback_query.message.answer("Сообщение отклонено.")

# Запуск бота
if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)