"""
Скрипт миграции для добавления поля image_filename в таблицу Event
"""
import sqlite3
import os

# Определяем путь к базе данных
base_dir = os.path.abspath(os.path.dirname(__file__))
instance_db_path = os.path.join(base_dir, 'instance', 'events.db')
default_db_path = os.path.join(base_dir, 'events.db')

# Используем существующую базу данных
if os.path.exists(instance_db_path):
    db_path = instance_db_path
elif os.path.exists(default_db_path):
    db_path = default_db_path
else:
    print("База данных не найдена!")
    exit(1)

print(f"Используется база данных: {db_path}")

# Подключаемся к базе данных
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Проверяем, существует ли уже поле image_filename
    cursor.execute("PRAGMA table_info(event)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'image_filename' in columns:
        print("Поле image_filename уже существует в таблице event")
    else:
        # Добавляем новое поле
        cursor.execute("ALTER TABLE event ADD COLUMN image_filename VARCHAR(255)")
        conn.commit()
        print("Поле image_filename успешно добавлено в таблицу event")
    
except Exception as e:
    print(f"Ошибка при миграции: {e}")
    conn.rollback()
finally:
    conn.close()

print("Миграция завершена!")
