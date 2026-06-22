import psycopg2
from psycopg2 import sql, extras
import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple

DATABASE_URL = os.getenv('DATABASE_URL')

def get_connection():
    """Получить соединение с PostgreSQL"""
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    """Инициализация базы данных: создание таблиц"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Таблица ремонтов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS repairs (
            id SERIAL PRIMARY KEY,
            car_number VARCHAR(20) NOT NULL,
            car_model VARCHAR(100),
            description TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'в работе',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            cost DECIMAL(10, 2),
            master VARCHAR(100),
            user_id BIGINT
        )
    """)
    
    # Таблица белого списка пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(100),
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    
    # Таблица для статистики (можно использовать для аналитики)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            id SERIAL PRIMARY KEY,
            stat_date DATE DEFAULT CURRENT_DATE,
            total_repairs INTEGER DEFAULT 0,
            completed_repairs INTEGER DEFAULT 0,
            total_cost DECIMAL(10, 2) DEFAULT 0
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ База данных PostgreSQL инициализирована")

# ============= РЕМОНТЫ =============

def add_repair(car_number: str, description: str, car_model: str = None, 
               master: str = None, user_id: int = None) -> int:
    """Добавить новый ремонт. Возвращает ID записи"""
    conn = get_connection()
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

def get_repair(repair_id: int) -> Optional[Dict]:
    """Получить ремонт по ID"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    
    cur.execute("SELECT * FROM repairs WHERE id = %s", (repair_id,))
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    return dict(result) if result else None

def get_all_repairs(status: str = None, limit: int = 100) -> List[Dict]:
    """Получить список ремонтов с фильтром по статусу"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    
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

def update_repair_status(repair_id: int, new_status: str, cost: float = None) -> bool:
    """Обновить статус ремонта и опционально стоимость"""
    conn = get_connection()
    cur = conn.cursor()
    
    if new_status == 'завершён' and cost is not None:
        cur.execute("""
            UPDATE repairs 
            SET status = %s, cost = %s, completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_status, cost, repair_id))
    elif new_status == 'завершён':
        cur.execute("""
            UPDATE repairs 
            SET status = %s, completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_status, repair_id))
    else:
        cur.execute("""
            UPDATE repairs 
            SET status = %s
            WHERE id = %s
        """, (new_status, repair_id))
    
    updated = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return updated

def get_repairs_by_car(car_number: str) -> List[Dict]:
    """Получить все ремонты по номеру машины"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    
    cur.execute("""
        SELECT * FROM repairs 
        WHERE car_number = %s 
        ORDER BY created_at DESC
    """, (car_number,))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in results]

def get_today_stats() -> Dict:
    """Получить статистику за сегодня"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    
    today = date.today()
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'завершён') as completed,
            COALESCE(SUM(cost), 0) as total_cost
        FROM repairs
        WHERE DATE(created_at) = %s
    """, (today,))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    return dict(result) if result else {'total': 0, 'completed': 0, 'total_cost': 0}

# ============= БЕЛЫЙ СПИСОК =============

def add_to_whitelist(user_id: int, username: str = None) -> bool:
    """Добавить пользователя в белый список"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            INSERT INTO whitelist (user_id, username)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE 
            SET is_active = TRUE, username = EXCLUDED.username
        """, (user_id, username))
        conn.commit()
        return True
    except Exception as e:
        print(f"Ошибка добавления в whitelist: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def remove_from_whitelist(user_id: int) -> bool:
    """Удалить пользователя из белого списка (деактивировать)"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE whitelist SET is_active = FALSE
        WHERE user_id = %s
    """, (user_id,))
    
    updated = cur.rowcount > 0
    conn.commit()
    cur.close()
    conn.close()
    return updated

def is_user_whitelisted(user_id: int) -> bool:
    """Проверить, есть ли пользователь в белом списке"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 1 FROM whitelist 
        WHERE user_id = %s AND is_active = TRUE
    """, (user_id,))
    
    result = cur.fetchone() is not None
    cur.close()
    conn.close()
    return result

def get_whitelist() -> List[Dict]:
    """Получить список всех активных пользователей в белом списке"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    
    cur.execute("""
        SELECT user_id, username, added_at 
        FROM whitelist 
        WHERE is_active = TRUE
        ORDER BY added_at DESC
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in results]

# ============= ЕЖЕДНЕВНАЯ СТАТИСТИКА =============

def update_daily_stats():
    """Обновить ежедневную статистику"""
    conn = get_connection()
    cur = conn.cursor()
    
    today = date.today()
    
    # Получаем статистику за сегодня
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'завершён') as completed,
            COALESCE(SUM(cost), 0) as total_cost
        FROM repairs
        WHERE DATE(created_at) = %s
    """, (today,))
    
    stats = cur.fetchone()
    
    cur.execute("""
        INSERT INTO daily_stats (stat_date, total_repairs, completed_repairs, total_cost)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (stat_date) DO UPDATE 
        SET total_repairs = EXCLUDED.total_repairs,
            completed_repairs = EXCLUDED.completed_repairs,
            total_cost = EXCLUDED.total_cost
    """, (today, stats[0], stats[1], stats[2]))
    
    conn.commit()
    cur.close()
    conn.close()

def get_weekly_stats() -> List[Dict]:
    """Получить статистику за последнюю неделю"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    
    cur.execute("""
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'завершён') as completed,
            COALESCE(SUM(cost), 0) as total_cost
        FROM repairs
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """)
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in results]

# Функция для тестирования подключения
def test_connection():
    """Проверить подключение к БД"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()
        cur.close()
        conn.close()
        print(f"✅ Подключение к PostgreSQL успешно: {version[0]}")
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к PostgreSQL: {e}")
        return False