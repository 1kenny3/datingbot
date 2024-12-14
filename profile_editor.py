from aiogram import types, Bot
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
import logging
from typing import List, Optional

from database import (
    get_profile, update_profile, get_user_interests,
    add_user_interests, get_all_interests, clear_user_interests
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния редактирования профиля
class ProfileEditStates(StatesGroup):
    waiting_for_choice = State()
    edit_name = State()
    edit_age = State()
    edit_gender = State()
    edit_looking_for = State()
    edit_city = State()
    edit_description = State()
    edit_photo = State()
    edit_interests = State()

def get_edit_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру для выбора параметра редактирования"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("✏️ Изменить имя"))
    keyboard.add(KeyboardButton("🔢 Изменить возраст"))
    keyboard.add(KeyboardButton("👤 Изменить пол"))
    keyboard.add(KeyboardButton("🔍 Изменить кого ищу"))
    keyboard.add(KeyboardButton("🌆 Изменить город"))
    keyboard.add(KeyboardButton("📝 Изменить описание"))
    keyboard.add(KeyboardButton("📷 Изменить фото"))
    keyboard.add(KeyboardButton("🎯 Изменить интересы"))
    keyboard.add(KeyboardButton("🔙 Вернуться"))
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
                callback_data=f"edit_interest_{interest_id}"
            )
        )
    
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        keyboard.row(*row)
    
    keyboard.row(InlineKeyboardButton(
        text="Готово ✅",
        callback_data="edit_interests_done"
    ))
    
    return keyboard

async def start_profile_editing(message: types.Message, state: FSMContext):
    """Начало редактирования профиля"""
    try:
        user_id = message.from_user.id
        profile = get_profile(user_id)
        
        if not profile:
            await message.answer("Сначала создайте профиль!")
            return
            
        await ProfileEditStates.waiting_for_choice.set()
        await message.answer(
            "Что вы хотите изменить?",
            reply_markup=get_edit_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error starting profile editing: {e}")
        await message.answer("Произошла ошибка при начале редактирования профиля.")

async def process_edit_choice(message: types.Message, state: FSMContext):
    """Обработка выбора параметра для редактирования"""
    try:
        choice = message.text
        
        if choice == "✏️ Изменить имя":
            await ProfileEditStates.edit_name.set()
            await message.answer(
                "Введите новое имя:",
                reply_markup=ReplyKeyboardRemove()
            )
            
        elif choice == "🔢 Изменить возраст":
            await ProfileEditStates.edit_age.set()
            await message.answer(
                "Введите новый возраст (число):",
                reply_markup=ReplyKeyboardRemove()
            )
            
        elif choice == "👤 Изменить пол":
            await ProfileEditStates.edit_gender.set()
            await message.answer(
                "Выберите пол:",
                reply_markup=get_gender_keyboard()
            )
            
        elif choice == "🔍 Изменить кого ищу":
            await ProfileEditStates.edit_looking_for.set()
            await message.answer(
                "Кого вы хотите найти?",
                reply_markup=get_looking_for_keyboard()
            )
            
        elif choice == "🌆 Изменить город":
            await ProfileEditStates.edit_city.set()
            await message.answer(
                "Введите новый город (или '-' чтобы убрать):",
                reply_markup=ReplyKeyboardRemove()
            )
            
        elif choice == "📝 Изменить описание":
            await ProfileEditStates.edit_description.set()
            await message.answer(
                "Введите новое описание:",
                reply_markup=ReplyKeyboardRemove()
            )
            
        elif choice == "📷 Изменить фото":
            await ProfileEditStates.edit_photo.set()
            await message.answer(
                "Отправьте новое фото:",
                reply_markup=ReplyKeyboardRemove()
            )
            
        elif choice == "🎯 Изменить интересы":
            await ProfileEditStates.edit_interests.set()
            user_id = message.from_user.id
            current_interests = get_user_interests(user_id)
            await message.answer(
                "Выберите ваши интересы (можно выбрать до 5):",
                reply_markup=get_interests_keyboard([int(i) for i in current_interests])
            )
            
        elif choice == "🔙 Вернуться":
            await state.finish()
            from main import get_main_keyboard  # Импортируем здесь во избежание циклического импорта
            await message.answer(
                "Вы вернулись в главное меню",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
            
    except Exception as e:
        logger.error(f"Error processing edit choice: {e}")
        await message.answer("Произошла ошибка при обработке выбора.")

async def process_edit_name(message: types.Message, state: FSMContext):
    """Обработка изменения имени"""
    try:
        new_name = message.text
        if len(new_name) < 2:
            await message.answer("Имя должно содержать хотя бы 2 символа. Попробуйте еще раз:")
            return
            
        user_id = message.from_user.id
        update_profile(user_id, name=new_name)
        await message.answer(
            "Имя успешно обновлено!",
            reply_markup=get_edit_keyboard()
        )
        await ProfileEditStates.waiting_for_choice.set()
            
    except Exception as e:
        logger.error(f"Error updating name: {e}")
        await message.answer("Произошла ошибка при обновлении имени.")

async def process_edit_age(message: types.Message, state: FSMContext):
    """Обработка изменения возраста"""
    try:
        if not message.text.isdigit():
            await message.answer("Возраст должен быть числом. Попробуйте еще раз:")
            return
            
        new_age = int(message.text)
        if new_age < 18 or new_age > 100:
            await message.answer("Возраст должен быть от 18 до 100 лет. Попробуйте еще раз:")
            return
            
        user_id = message.from_user.id
        update_profile(user_id, age=new_age)
        await message.answer(
            "Возраст успешно обновлен!",
            reply_markup=get_edit_keyboard()
        )
        await ProfileEditStates.waiting_for_choice.set()
            
    except Exception as e:
        logger.error(f"Error updating age: {e}")
        await message.answer("Произошла ошибка при обновлении возраста.")

async def process_edit_gender(message: types.Message, state: FSMContext):
    """Обработка изменения пола"""
    try:
        gender_map = {
            "👨 Мужской": "M",
            "👩 Женский": "F"
        }
        
        if message.text not in gender_map:
            await message.answer("Пожалуйста, выберите пол, используя кнопки.")
            return
            
        user_id = message.from_user.id
        update_profile(user_id, gender=gender_map[message.text])
        await message.answer(
            "Пол успешно обновлен!",
            reply_markup=get_edit_keyboard()
        )
        await ProfileEditStates.waiting_for_choice.set()
            
    except Exception as e:
        logger.error(f"Error updating gender: {e}")
        await message.answer("Произошла ошибка при обновлении пола.")

async def process_edit_looking_for(message: types.Message, state: FSMContext):
    """Обработка изменения предпочтений поиска"""
    try:
        looking_for_map = {
            "👨 Мужчин": "M",
            "👩 Женщин": "F",
            "👥 Всех": "MF"
        }
        
        if message.text not in looking_for_map:
            await message.answer("Пожалуйста, выберите предпочтение, используя кнопки.")
            return
            
        user_id = message.from_user.id
        update_profile(user_id, looking_for=looking_for_map[message.text])
        await message.answer(
            "Предпочтения поиска успешно обновлены!",
            reply_markup=get_edit_keyboard()
        )
        await ProfileEditStates.waiting_for_choice.set()
            
    except Exception as e:
        logger.error(f"Error updating looking_for: {e}")
        await message.answer("Произошла ошибка при обновлении предпочтений поиска.")

async def process_edit_city(message: types.Message, state: FSMContext):
    """Обработка изменения города"""
    try:
        new_city = None if message.text == '-' else message.text
        user_id = message.from_user.id
        update_profile(user_id, city=new_city)
        await message.answer(
            "Город успешно обновлен!",
            reply_markup=get_edit_keyboard()
        )
        await ProfileEditStates.waiting_for_choice.set()
            
    except Exception as e:
        logger.error(f"Error updating city: {e}")
        await message.answer("Произошла ошибка при обновлении города.")

async def process_edit_description(message: types.Message, state: FSMContext):
    """Обработка изменения описания"""
    try:
        new_description = message.text
        if len(new_description) < 10:
            await message.answer("Описание должно содержать хотя бы 10 символов. Попробуйте еще раз:")
            return
            
        user_id = message.from_user.id
        update_profile(user_id, description=new_description)
        await message.answer(
            "Описание успешно обновлено!",
            reply_markup=get_edit_keyboard()
        )
        await ProfileEditStates.waiting_for_choice.set()
            
    except Exception as e:
        logger.error(f"Error updating description: {e}")
        await message.answer("Произошла ошибка при обновлении описания.")

async def process_edit_photo(message: types.Message, state: FSMContext):
    """Обработка изменения фото"""
    try:
        if not message.photo:
            await message.answer("Пожалуйста, отправьте фото.")
            return
            
        photo = message.photo[-1]
        photo_id = photo.file_id
        
        try:
            # Проверяем валидность file_id
            bot = Bot.get_current()
            await bot.get_file(photo_id)
        except Exception as e:
            logger.error(f"Invalid photo_id: {e}")
            await message.answer("Ошибка при обработке фото. Пожалуйста, отправьте другое фото.")
            return
            
        user_id = message.from_user.id
        update_profile(user_id, photo_id=photo_id)
        await message.answer(
            "Фото успешно обновлено!",
            reply_markup=get_edit_keyboard()
        )
        await ProfileEditStates.waiting_for_choice.set()
            
    except Exception as e:
        logger.error(f"Error updating photo: {e}")
        await message.answer("Произошла ошибка при обновлении фото.")

async def process_edit_interest_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработка выбора интересов"""
    try:
        await callback_query.answer()
        
        interest_id = int(callback_query.data.split('_')[2])
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
        logger.error(f"Error in process_edit_interest_selection: {e}")
        await callback_query.message.answer("Произошла ошибка при выборе интересов")

async def process_edit_interests_done(callback_query: types.CallbackQuery, state: FSMContext):
    """Завершение редактирования интересов"""
    try:
        data = await state.get_data()
        selected_interests = data.get('selected_interests', [])
        
        if not selected_interests:
            await callback_query.answer("Выберите хотя бы один интерес!")
            return
        
        user_id = callback_query.from_user.id
        clear_user_interests(user_id)
        add_user_interests(user_id, selected_interests)
        
        await callback_query.message.answer(
            "Интересы успешно обновлены!",
            reply_markup=get_edit_keyboard()
        )
        await ProfileEditStates.waiting_for_choice.set()
        
    except Exception as e:
        logger.error(f"Error in process_edit_interests_done: {e}")
        await callback_query.message.answer("Произошла ошибка при обновлении интересов")

def register_handlers(dp):
    """Регистрация всех обработчиков"""
    dp.register_message_handler(
        start_profile_editing,
        lambda message: message.text == "📝 Редактировать профиль",
        state="*"
    )
    
    dp.register_message_handler(
        process_edit_choice,
        state=ProfileEditStates.waiting_for_choice
    )
    
    dp.register_message_handler(
        process_edit_name,
        state=ProfileEditStates.edit_name
    )
    
    dp.register_message_handler(
        process_edit_age,
        state=ProfileEditStates.edit_age
    )
    
    dp.register_message_handler(
        process_edit_gender,
        state=ProfileEditStates.edit_gender
    )
    
    dp.register_message_handler(
        process_edit_looking_for,
        state=ProfileEditStates.edit_looking_for
    )
    
    dp.register_message_handler(
        process_edit_city,
        state=ProfileEditStates.edit_city
    )
    
    dp.register_message_handler(
        process_edit_description,
        state=ProfileEditStates.edit_description
    )
    
    dp.register_message_handler(
        process_edit_photo,
        content_types=['photo'],
        state=ProfileEditStates.edit_photo
    )
    
    dp.register_callback_query_handler(
        process_edit_interest_selection,
        lambda c: c.data.startswith('edit_interest_'),
        state=ProfileEditStates.edit_interests
    )
    
    dp.register_callback_query_handler(
        process_edit_interests_done,
        lambda c: c.data == 'edit_interests_done',
        state=ProfileEditStates.edit_interests
    )