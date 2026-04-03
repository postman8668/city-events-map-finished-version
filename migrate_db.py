"""
Скрипт миграции базы данных для добавления полей status и creator_id в таблицу Event
"""
import sqlite3
import os

def migrate_database():
    # Определяем путь к базе данных
    base_dir = os.path.abspath(os.path.dirname(__file__))
    instance_db_path = os.path.join(base_dir, 'instance', 'events.db')
    default_db_path = os.path.join(base_dir, 'events.db')
    
    db_path = instance_db_path if os.path.exists(instance_db_path) else default_db_path
    
    if not os.path.exists(db_path):
        print(f"База данных не найдена по пути: {db_path}")
        print("Создайте базу данных, запустив приложение.")
        return
    
    print(f"Подключение к базе данных: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существуют ли уже колонки
        cursor.execute("PRAGMA table_info(event)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"Текущие колонки в таблице event: {columns}")
        
        # Добавляем колонку status, если её нет
        if 'status' not in columns:
            print("Добавление колонки 'status'...")
            cursor.execute("ALTER TABLE event ADD COLUMN status VARCHAR(20) DEFAULT 'approved' NOT NULL")
            print("✓ Колонка 'status' добавлена")
        else:
            print("✓ Колонка 'status' уже существует")
        
        # Добавляем колонку creator_id, если её нет
        if 'creator_id' not in columns:
            print("Добавление колонки 'creator_id'...")
            cursor.execute("ALTER TABLE event ADD COLUMN creator_id INTEGER")
            print("✓ Колонка 'creator_id' добавлена")
        else:
            print("✓ Колонка 'creator_id' уже существует")
        
        # Обновляем существующие события - устанавливаем статус 'approved'
        cursor.execute("UPDATE event SET status = 'approved' WHERE status IS NULL OR status = ''")
        updated_rows = cursor.rowcount
        print(f"✓ Обновлено {updated_rows} событий со статусом 'approved'")
        
        conn.commit()
        print("\n✅ Миграция успешно завершена!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при миграции: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 50)
    print("Миграция базы данных")
    print("=" * 50)
    migrate_database()
