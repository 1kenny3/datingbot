import sqlite3
from typing import Optional, List, Tuple
import logging
from datetime import datetime

# Настройка логирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Создаем обработчик для вывода в файл
file_handler = logging.FileHandler('database.log')
file_handler.setLevel(logging.INFO)

# Создаем обработчик для вывода в консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Создаем форматтер для логов
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Добавляем обработчики к логгеру
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Константы
DATABASE_PATH = 'dating_bot.db'

def init_db():
    """Инициализация базы данных"""
    conn = get_connection()
    try:
        c = conn.cursor()
        
        # Создание таблицы профилей с полем username
        c.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                description TEXT NOT NULL,
                photo_id TEXT NOT NULL,
                gender TEXT NOT NULL,
                looking_for TEXT NOT NULL,
                city TEXT,
                username TEXT,  -- Добавлено поле username
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Попытка добавить столбец username, если его нет
        try:
            c.execute('ALTER TABLE profiles ADD COLUMN username TEXT;')
            logger.info("Added username column to profiles table")
        except sqlite3.OperationalError:
            logger.info("Username column already exists")
        
        # Создание таблицы интересов
        c.execute('''
            CREATE TABLE IF NOT EXISTS interests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')
        
        # Создание таблицы интересов пользователей
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_interests (
                user_id INTEGER,
                interest_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES profiles (user_id),
                FOREIGN KEY (interest_id) REFERENCES interests (id),
                PRIMARY KEY (user_id, interest_id)
            )
        ''')
        
        # Создание таблицы лайков
        c.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                user_id INTEGER,
                liked_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES profiles (user_id),
                FOREIGN KEY (liked_user_id) REFERENCES profiles (user_id),
                PRIMARY KEY (user_id, liked_user_id)
            )
        ''')
        
        # Создание таблицы просмотренных профилей
        c.execute('''
            CREATE TABLE IF NOT EXISTS viewed_profiles (
                user_id INTEGER,
                viewed_user_id INTEGER,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES profiles (user_id),
                FOREIGN KEY (viewed_user_id) REFERENCES profiles (user_id),
                PRIMARY KEY (user_id, viewed_user_id)
            )
        ''')
        
        # Создание таблицы жалоб
        c.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                from_user_id INTEGER,
                reported_user_id INTEGER,
                reason TEXT,  -- Добавлено поле для причины жалобы
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES profiles (user_id),
                FOREIGN KEY (reported_user_id) REFERENCES profiles (user_id),
                PRIMARY KEY (from_user_id, reported_user_id)
            )
        ''')
        
        # Создание таблицы блокировок
        c.execute('''
            CREATE TABLE IF NOT EXISTS blocks (
                user_id INTEGER,
                blocked_user_id INTEGER,
                reason TEXT,  -- Добавлено поле для причины блокировки
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES profiles (user_id),
                FOREIGN KEY (blocked_user_id) REFERENCES profiles (user_id),
                PRIMARY KEY (user_id, blocked_user_id)
            )
        ''')
        
        # Создание индексов для оптимизации
        c.execute('CREATE INDEX IF NOT EXISTS idx_likes_user ON likes(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_likes_liked_user ON likes(liked_user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_viewed_user ON viewed_profiles(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_user_interests ON user_interests(user_id)')
        
        conn.commit()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()

# ... продолжение следует ...
def get_connection():
    """Создает и возвращает соединение с БД"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        logger.info(f"Successfully connected to database: {DATABASE_PATH}")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise

def execute_query(query: str, params: tuple = (), fetch: bool = False):
    """Выполняет запрос к БД с обработкой ошибок"""
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        logger.debug(f"Executing query: {query} with params: {params}")
        cursor.execute(query, params)
        
        if fetch:
            result = cursor.fetchall()
            logger.debug(f"Query returned {len(result)} results")
        else:
            connection.commit()
            result = None
            logger.debug("Query executed successfully")
            
        return result
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}\nQuery: {query}\nParams: {params}")
        if connection:
            connection.rollback()
            logger.info("Transaction rolled back")
        raise
    finally:
        if connection:
            connection.close()
            logger.debug("Database connection closed")


def get_profile(user_id: int) -> Optional[tuple]:
    """Получает профиль пользователя"""
    try:
        query = """
            SELECT user_id, name, age, description, photo_id, gender, looking_for, city, username
            FROM profiles WHERE user_id = ?
        """
        result = execute_query(query, (user_id,), fetch=True)
        logger.info(f"Retrieved profile for user {user_id}: {'Found' if result else 'Not found'}")
        if result:
            logger.debug(f"Profile data: {result[0]}")
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting profile for user {user_id}: {e}")
        return None

def add_profile(user_id: int, name: str, age: int, description: str, 
                photo_id: str, gender: str, looking_for: str, city: Optional[str], username: Optional[str] = None):
    """Добавляет или обновляет профиль пользователя"""
    try:
        query = '''
            INSERT OR REPLACE INTO profiles 
            (user_id, name, age, description, photo_id, gender, looking_for, city, username, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''
        execute_query(query, (user_id, name, age, description, photo_id, 
                            gender, looking_for, city, username))
        logger.info(f"Profile added/updated for user {user_id} with username {username}")
    except Exception as e:
        logger.error(f"Error adding/updating profile for user {user_id}: {e}")
        raise

def get_matching_profiles(user_id: int, gender: str, looking_for: str, exclude_viewed: bool = True) -> List[tuple]:
    """Получает список подходящих анкет"""
    try:
        query = '''
            SELECT 
                p.user_id,
                p.name,
                p.age,
                p.description,
                p.photo_id,
                COUNT(DISTINCT ui1.interest_id) as common_interests,
                ABS(p.age - (SELECT age FROM profiles WHERE user_id = ?)) as age_diff
            FROM profiles p
            LEFT JOIN user_interests ui1 ON p.user_id = ui1.user_id
            LEFT JOIN user_interests ui2 ON ui1.interest_id = ui2.interest_id AND ui2.user_id = ?
            WHERE p.user_id != ?
            AND (
                ? = 'MF'
                OR 
                (? = 'M' AND p.gender = 'M')
                OR 
                (? = 'F' AND p.gender = 'F')
            )
        '''
        
        if exclude_viewed:
            query += '''
                AND NOT EXISTS (
                    SELECT 1 FROM viewed_profiles 
                    WHERE user_id = ? AND viewed_user_id = p.user_id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM blocks
                    WHERE (user_id = ? AND blocked_user_id = p.user_id)
                       OR (user_id = p.user_id AND blocked_user_id = ?)
                )
            '''
        
        query += '''
            GROUP BY p.user_id, p.name, p.age, p.description, p.photo_id
            ORDER BY common_interests DESC, age_diff ASC
            LIMIT 50
        '''
        
        params = [user_id, user_id, user_id, looking_for, looking_for, looking_for]
        if exclude_viewed:
            params.extend([user_id, user_id, user_id])

        results = execute_query(query, tuple(params), fetch=True)
        logger.info(f"Found {len(results)} matching profiles for user {user_id}")
        return results
    except Exception as e:
        logger.error(f"Error getting matching profiles for user {user_id}: {e}")
        return []

def add_like(from_user_id: int, to_user_id: int):
    """Добавляет лайк"""
    try:
        query = "INSERT OR REPLACE INTO likes (user_id, liked_user_id) VALUES (?, ?)"
        execute_query(query, (from_user_id, to_user_id))
        logger.info(f"Like added: from {from_user_id} to {to_user_id}")
    except Exception as e:
        logger.error(f"Error adding like from {from_user_id} to {to_user_id}: {e}")
        raise

# ... продолжение следует ...
def check_mutual_like(user1_id: int, user2_id: int) -> bool:
    """Проверяет наличие взаимных лайков"""
    try:
        query = '''
            SELECT COUNT(*) FROM likes 
            WHERE (user_id = ? AND liked_user_id = ?)
            AND EXISTS (
                SELECT 1 FROM likes 
                WHERE user_id = ? AND liked_user_id = ?
            )
        '''
        result = execute_query(query, (user1_id, user2_id, user2_id, user1_id), fetch=True)
        return bool(result and result[0][0])
    except Exception as e:
        logger.error(f"Error checking mutual like between {user1_id} and {user2_id}: {e}")
        return False

def add_viewed_profile(user_id: int, viewed_user_id: int):
    """Отмечает профиль как просмотренный"""
    try:
        query = "INSERT OR REPLACE INTO viewed_profiles (user_id, viewed_user_id) VALUES (?, ?)"
        execute_query(query, (user_id, viewed_user_id))
        logger.info(f"Viewed profile added: {user_id} viewed {viewed_user_id}")
    except Exception as e:
        logger.error(f"Error adding viewed profile: {e}")
        raise

def get_user_interests(user_id: int) -> List[str]:
    """Получает список интересов пользователя"""
    try:
        query = '''
            SELECT i.name 
            FROM interests i
            JOIN user_interests ui ON i.id = ui.interest_id
            WHERE ui.user_id = ?
        '''
        result = execute_query(query, (user_id,), fetch=True)
        return [row[0] for row in result]
    except Exception as e:
        logger.error(f"Error getting interests for user {user_id}: {e}")
        return []

def get_all_interests() -> List[tuple]:
    """Получает список всех интересов"""
    try:
        query = "SELECT id, name FROM interests ORDER BY name"
        result = execute_query(query, fetch=True)
        logger.info(f"Retrieved {len(result)} interests")
        return result
    except Exception as e:
        logger.error(f"Error getting interests: {e}")
        return []

def clear_user_interests(user_id: int):
    """Удаляет все интересы пользователя"""
    try:
        query = "DELETE FROM user_interests WHERE user_id = ?"
        execute_query(query, (user_id,))
        logger.info(f"Cleared interests for user {user_id}")
    except Exception as e:
        logger.error(f"Error clearing interests for user {user_id}: {e}")
        raise

def add_user_interests(user_id: int, interests: List[int]):
    """Добавляет интересы пользователя"""
    try:
        query = "INSERT INTO user_interests (user_id, interest_id) VALUES (?, ?)"
        for interest_id in interests:
            execute_query(query, (user_id, interest_id))
        logger.info(f"Added {len(interests)} interests for user {user_id}")
    except Exception as e:
        logger.error(f"Error adding interests for user {user_id}: {e}")
        raise

def get_recent_likes(user_id: int, limit: int = 10) -> List[tuple]:
    """Получает последние лайки пользователя"""
    try:
        query = '''
            SELECT 
                l.user_id,
                p.name,
                p.age,
                p.description,
                p.photo_id,
                l.created_at
            FROM likes l
            JOIN profiles p ON l.user_id = p.user_id
            WHERE l.liked_user_id = ?
            AND NOT EXISTS (
                SELECT 1 FROM likes 
                WHERE user_id = ? AND liked_user_id = l.user_id
            )
            ORDER BY l.created_at DESC
            LIMIT ?
        '''
        result = execute_query(query, (user_id, user_id, limit), fetch=True)
        logger.info(f"Retrieved {len(result)} recent likes for user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Error getting recent likes for user {user_id}: {e}")
        return []

def add_report(from_user_id: int, reported_user_id: int):
    """Добавляет жалобу"""
    try:
        query = "INSERT OR REPLACE INTO reports (from_user_id, reported_user_id) VALUES (?, ?)"
        execute_query(query, (from_user_id, reported_user_id))
        logger.info(f"Report added: from {from_user_id} on {reported_user_id}")
    except Exception as e:
        logger.error(f"Error adding report: {e}")
        raise

def add_block(user_id: int, blocked_user_id: int):
    """Добавляет блокировку"""
    try:
        query = "INSERT OR REPLACE INTO blocks (user_id, blocked_user_id) VALUES (?, ?)"
        execute_query(query, (user_id, blocked_user_id))
        logger.info(f"Block added: {user_id} blocked {blocked_user_id}")
    except Exception as e:
        logger.error(f"Error adding block: {e}")
        raise

def init_interests():
    """Инициализация базовых интересов"""
    interests = [
        "Спорт",
        "Музыка",
        "Кино",
        "Путешествия",
        "Книги",
        "Искусство",
        "Фотография",
        "Кулинария",
        "Танцы",
        "Игры",
        "Технологии",
        "Природа",
        "Животные",
        "Йога",
        "Медитация"
    ]
    
    try:
        query = "INSERT OR IGNORE INTO interests (name) VALUES (?)"
        for interest in interests:
            execute_query(query, (interest,))
        logger.info(f"Initialized {len(interests)} basic interests")
    except Exception as e:
        logger.error(f"Error initializing interests: {e}")
        raise
# В конце файла database.py
init_db()
init_interests()  # Добавьте эту строку

def get_last_like(user_id: int) -> Optional[tuple]:
    """Получает информацию о последнем лайке"""
    try:
        query = '''
            SELECT 
                l.user_id,
                p.name,
                p.age,
                p.photo_id,
                l.created_at
            FROM likes l
            JOIN profiles p ON l.user_id = p.user_id
            WHERE l.liked_user_id = ?
            ORDER BY l.created_at DESC
            LIMIT 1
        '''
        result = execute_query(query, (user_id,), fetch=True)
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting last like for user {user_id}: {e}")
        return None
    
def update_profile(user_id: int, **kwargs) -> bool:
    """
    Обновляет профиль пользователя.
    
    Args:
        user_id (int): ID пользователя
        **kwargs: Поля для обновления (name, age, description, photo_id, gender, looking_for, city)
    
    Returns:
        bool: True если обновление успешно, False в противном случае
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Формируем SQL запрос для обновления
        update_fields = []
        values = []
        
        for key, value in kwargs.items():
            update_fields.append(f"{key} = ?")
            values.append(value)
            
        if not update_fields:
            return False
            
        values.append(user_id)
        
        query = f"""
            UPDATE profiles 
            SET {', '.join(update_fields)}, last_active = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """
        
        cursor.execute(query, values)
        conn.commit()
        logger.info(f"Profile updated for user {user_id}: {kwargs}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()

def get_all_users() -> list:
    """Получает ID всех пользователей"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM profiles")
        
        # Возвращаем список ID пользователей
        return [row[0] for row in cursor.fetchall()]
        
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_last_active(user_id: int):
    """Обновляет время последней активности пользователя"""
    try:
        query = "UPDATE profiles SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?"
        execute_query(query, (user_id,))
        logger.debug(f"Updated last_active for user {user_id}")
    except Exception as e:
        logger.error(f"Error updating last_active for user {user_id}: {e}")
        raise

def update_username(user_id: int, username: str):
    """Обновляет username пользователя"""
    try:
        query = "UPDATE profiles SET username = ? WHERE user_id = ?"
        execute_query(query, (username, user_id))
        logger.info(f"Updated username for user {user_id}: {username}")
    except Exception as e:
        logger.error(f"Error updating username for user {user_id}: {e}")
        raise

def get_users_by_interests(interest_ids: List[int]) -> List[int]:
    """Получает список пользователей, у которых есть указанные интересы"""
    try:
        query = '''
            SELECT DISTINCT user_id 
            FROM user_interests 
            WHERE interest_id IN ({})
        '''.format(','.join(['?'] * len(interest_ids)))
        
        result = execute_query(query, tuple(interest_ids), fetch=True)
        return [row[0] for row in result]
    except Exception as e:
        logger.error(f"Error getting users by interests: {e}")
        return []

# Инициализация базы данных при импорте модуля
init_db()