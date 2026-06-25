import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем URL базы данных из переменных окружения
DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    """Получить соединение с базой данных"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        return None

def test_connection():
    """Проверить подключение к БД"""
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка тестирования подключения: {e}")
        return False

def init_db():
    """Инициализация базы данных - создание таблиц"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Не удалось подключиться к БД для инициализации")
            return False
        
        cur = conn.cursor()
        
        # Таблица ремонтов
        cur.execute("""
            CREATE TABLE IF NOT EXISTS repairs (
                id SERIAL PRIMARY KEY,
                car_number VARCHAR(20) NOT NULL,
                car_model VARCHAR(100),
                description TEXT NOT NULL,
                master VARCHAR(100),
                status VARCHAR(50) DEFAULT 'в работе',
                cost DECIMAL(10, 2),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP,
                user_id BIGINT
            )
        """)
        
        # Таблица белого списка
        cur.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(100),
                added_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("База данных инициализирована успешно")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        return False

def add_to_whitelist(user_id: int, username: str = None) -> bool:
    """Добавить пользователя в белый список"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO whitelist (user_id, username)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
        """, (user_id, username))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления в белый список: {e}")
        return False

def is_user_whitelisted(user_id: int) -> bool:
    """Проверить, есть ли пользователь в белом списке"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        cur.execute("SELECT id FROM whitelist WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        logger.error(f"Ошибка проверки белого списка: {e}")
        return False

def add_repair(car_number: str, description: str, car_model: str = None, 
               master: str = None, user_id: int = None) -> Optional[int]:
    """Добавить новый ремонт"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO repairs (car_number, car_model, description, master, user_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (car_number, car_model, description, master, user_id))
        
        repair_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return repair_id
    except Exception as e:
        logger.error(f"Ошибка добавления ремонта: {e}")
        return None

def get_repair(repair_id: int) -> Optional[Dict]:
    """Получить ремонт по ID"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM repairs WHERE id = %s", (repair_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"Ошибка получения ремонта: {e}")
        return None

def update_repair_field(repair_id: int, field: str, value) -> bool:
    """Обновить конкретное поле ремонта"""
    try:
        # Разрешенные поля для обновления
        allowed_fields = ['car_number', 'car_model', 'description', 'master', 'cost']
        
        if field not in allowed_fields:
            logger.error(f"Поле {field} не разрешено для обновления")
            return False
        
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        # Для cost проверяем тип
        if field == 'cost':
            value = float(value)
        
        query = f"UPDATE repairs SET {field} = %s, updated_at = NOW() WHERE id = %s"
        cur.execute(query, (value, repair_id))
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления поля {field}: {e}")
        return False

def update_repair_status(repair_id: int, status: str, cost: float = None) -> bool:
    """Обновить статус ремонта"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cur = conn.cursor()
        
        if status == 'завершён' and cost is not None:
            cur.execute("""
                UPDATE repairs 
                SET status = %s, cost = %s, completed_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (status, cost, repair_id))
        else:
            cur.execute("""
                UPDATE repairs 
                SET status = %s, updated_at = NOW()
                WHERE id = %s
            """, (status, repair_id))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обновления статуса: {e}")
        return False

def get_all_repairs(status: str = None, limit: int = 50) -> List[Dict]:
    """Получить все ремонты с фильтром по статусу"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if status:
            cur.execute("""
                SELECT * FROM repairs 
                WHERE status = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (status, limit))
        else:
            cur.execute("""
                SELECT * FROM repairs 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in results]
        
    except Exception as e:
        logger.error(f"Ошибка получения списка ремонтов: {e}")
        return []

def get_repairs_by_car(car_number: str) -> List[Dict]:
    """Найти ремонты по номеру машины"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM repairs 
            WHERE car_number ILIKE %s 
            ORDER BY created_at DESC
        """, (f'%{car_number}%',))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in results]
        
    except Exception as e:
        logger.error(f"Ошибка поиска по номеру: {e}")
        return []

def get_today_stats() -> Dict:
    """Получить статистику за сегодня"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'total': 0, 'completed': 0, 'total_cost': 0.0}
        
        cur = conn.cursor()
        today = datetime.now().date()
        
        # Всего ремонтов за сегодня
        cur.execute("""
            SELECT COUNT(*) FROM repairs 
            WHERE DATE(created_at) = %s
        """, (today,))
        total = cur.fetchone()[0]
        
        # Завершенных ремонтов за сегодня
        cur.execute("""
            SELECT COUNT(*) FROM repairs 
            WHERE DATE(completed_at) = %s AND status = 'завершён'
        """, (today,))
        completed = cur.fetchone()[0]
        
        # Сумма за сегодня
        cur.execute("""
            SELECT COALESCE(SUM(cost), 0) FROM repairs 
            WHERE DATE(completed_at) = %s AND status = 'завершён'
        """, (today,))
        total_cost = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return {
            'total': total,
            'completed': completed,
            'total_cost': float(total_cost)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики за сегодня: {e}")
        return {'total': 0, 'completed': 0, 'total_cost': 0.0}

def get_weekly_stats() -> List[Dict]:
    """Получить статистику за неделю"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        week_ago = datetime.now() - timedelta(days=7)
        
        cur.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'завершён' THEN 1 END) as completed,
                COALESCE(SUM(CASE WHEN status = 'завершён' THEN cost ELSE 0 END), 0) as total_cost
            FROM repairs
            WHERE created_at >= %s
            GROUP BY DATE(created_at)
            ORDER BY DATE(created_at) DESC
        """, (week_ago,))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in results]
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики за неделю: {e}")
        return []
