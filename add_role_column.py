"""
Скрипт для добавления колонки role в таблицу user
"""
from app import app, db, User

with app.app_context():
    # Добавляем колонку role
    try:
        with db.engine.connect() as conn:
            # Проверяем, существует ли колонка
            result = conn.execute(db.text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result]
            
            if 'role' not in columns:
                print("Добавляем колонку role...")
                conn.execute(db.text("ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'user' NOT NULL"))
                conn.commit()
                print("Колонка role успешно добавлена!")
                
                # Устанавливаем роль admin для пользователя admin
                conn.execute(db.text("UPDATE user SET role = 'admin' WHERE username = 'admin'"))
                conn.commit()
                print("Роль admin установлена для пользователя admin")
            else:
                print("Колонка role уже существует")
                
    except Exception as e:
        print(f"Ошибка: {e}")
        db.session.rollback()

print("Миграция завершена!")
