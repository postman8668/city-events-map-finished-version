"""
Скрипт для автоматического подтверждения email у существующих пользователей
Запускать один раз после добавления системы подтверждения email
"""

from app import app, db, User
from datetime import datetime

def confirm_existing_users():
    """Подтверждает email у всех существующих пользователей"""
    with app.app_context():
        try:
            # Находим всех пользователей с неподтвержденным email
            unconfirmed_users = User.query.filter_by(email_confirmed=False).all()
            
            if not unconfirmed_users:
                print("✓ Все пользователи уже подтверждены")
                return
            
            # Подтверждаем email у всех существующих пользователей
            for user in unconfirmed_users:
                user.email_confirmed = True
                user.email_confirmed_at = datetime.utcnow()
                print(f"✓ Подтвержден email для пользователя: {user.username}")
            
            db.session.commit()
            print(f"\n✓ Успешно подтверждено {len(unconfirmed_users)} пользователей")
            print("✓ Теперь только новые пользователи должны подтверждать email")
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ Ошибка: {e}")

if __name__ == '__main__':
    print("Подтверждение email для существующих пользователей...")
    confirm_existing_users()
