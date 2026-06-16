"""
Тестовый скрипт для проверки подсчета приближающихся событий
"""
from app import app, db, User, Event, SavedEvent, belarus_now
from datetime import timedelta

with app.app_context():
    # Получаем первого пользователя
    user = User.query.first()
    if not user:
        print("Нет пользователей в базе данных")
        exit()
    
    print(f"Пользователь: {user.username}")
    
    # Получаем события пользователя
    saved_events = SavedEvent.query.filter_by(user_id=user.id).all()
    print(f"Всего событий: {len(saved_events)}")
    
    # Подсчитываем приближающиеся события
    now = belarus_now()
    today = now.date()
    in_week = today + timedelta(days=7)
    
    upcoming_count = 0
    for saved_event in saved_events:
        event = saved_event.event
        if event and event.date >= today and event.date <= in_week:
            upcoming_count += 1
            days_until = (event.date - today).days
            print(f"  - {event.title}: {event.date} (через {days_until} дн.)")
    
    print(f"\nПриближающихся событий (в течение 7 дней): {upcoming_count}")
