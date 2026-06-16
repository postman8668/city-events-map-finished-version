"""
Скрипт для удаления всех уведомлений о событиях
"""
from app import app, db, Notification

with app.app_context():
    # Удаляем все уведомления
    deleted = Notification.query.delete(synchronize_session=False)
    
    db.session.commit()
    print(f"Удалено уведомлений: {deleted}")

