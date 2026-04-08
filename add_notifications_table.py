"""
Скрипт для создания таблицы notification
"""
from app import app, db

with app.app_context():
    try:
        with db.engine.connect() as conn:
            # Создаем таблицу notification
            conn.execute(db.text("""
                CREATE TABLE IF NOT EXISTS notification (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message VARCHAR(500) NOT NULL,
                    type VARCHAR(20) DEFAULT 'info',
                    is_read BOOLEAN DEFAULT 0,
                    created_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )
            """))
            conn.commit()
            print("Таблица notification успешно создана!")
    except Exception as e:
        print(f"Ошибка: {e}")
        db.session.rollback()

print("Миграция завершена!")
