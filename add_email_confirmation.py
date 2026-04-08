from app import app, db, User
from datetime import datetime

with app.app_context():
    try:
        # Добавляем новые колонки
        db.session.execute(db.text('ALTER TABLE user ADD COLUMN email_confirmed BOOLEAN DEFAULT 0'))
        db.session.execute(db.text('ALTER TABLE user ADD COLUMN email_confirmed_at DATETIME'))
        db.session.commit()
        print("✓ Колонки добавлены успешно")
        
        # Подтверждаем email для существующих пользователей
        users = User.query.all()
        for user in users:
            user.email_confirmed = True
            user.email_confirmed_at = datetime.now()
        db.session.commit()
        print(f"✓ Email подтвержден для {len(users)} существующих пользователей")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        db.session.rollback()
