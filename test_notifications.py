"""
Скрипт для тестирования системы уведомлений о приближающихся событиях
"""
from app import app, db, Event, User, SavedEvent, Notification, belarus_now
from datetime import date, time, timedelta

def create_test_events():
    """Создает тестовые события на ближайшие дни"""
    with app.app_context():
        today = date.today()
        tomorrow = today + timedelta(days=1)
        in_three_days = today + timedelta(days=3)
        in_week = today + timedelta(days=7)
        
        # Проверяем, есть ли тестовый пользователь
        test_user = User.query.filter_by(username='testuser').first()
        if not test_user:
            test_user = User(username='testuser', email='test@example.com', is_active=True)
            test_user.set_password('test123')
            db.session.add(test_user)
            db.session.commit()
            print(f"Создан тестовый пользователь: testuser / test123")
        
        # Создаем события на разные даты
        test_events = [
            {
                'title': 'Событие завтра',
                'date': tomorrow,
                'description': 'Тестовое событие на завтра'
            },
            {
                'title': 'Событие через 3 дня',
                'date': in_three_days,
                'description': 'Тестовое событие через 3 дня'
            },
            {
                'title': 'Событие через неделю',
                'date': in_week,
                'description': 'Тестовое событие через неделю'
            }
        ]
        
        created_events = []
        for event_data in test_events:
            # Проверяем, нет ли уже такого события
            existing = Event.query.filter_by(
                title=event_data['title'],
                date=event_data['date']
            ).first()
            
            if not existing:
                event = Event(
                    title=event_data['title'],
                    description=event_data['description'],
                    date=event_data['date'],
                    time=time(14, 0),
                    location='Тестовая локация',
                    latitude=55.485833,
                    longitude=28.758333,
                    category='Тестирование',
                    interests='["тест"]',
                    price=0.0,
                    status='approved'
                )
                db.session.add(event)
                db.session.commit()
                created_events.append(event)
                print(f"Создано событие: {event.title} на {event.date}")
            else:
                created_events.append(existing)
                print(f"Событие уже существует: {existing.title}")
        
        # Регистрируем пользователя на все события
        for event in created_events:
            existing_saved = SavedEvent.query.filter_by(
                user_id=test_user.id,
                event_id=event.id
            ).first()
            
            if not existing_saved:
                saved_event = SavedEvent(
                    user_id=test_user.id,
                    event_id=event.id
                )
                db.session.add(saved_event)
                print(f"Пользователь зарегистрирован на: {event.title}")
        
        db.session.commit()
        print(f"\nВсего создано/найдено событий: {len(created_events)}")
        print(f"Пользователь testuser зарегистрирован на все события")
        
        return test_user, created_events

def test_notification_system():
    """Тестирует систему уведомлений"""
    with app.app_context():
        from app import check_upcoming_events
        
        print("\n=== Запуск проверки приближающихся событий ===")
        check_upcoming_events()
        
        # Проверяем созданные уведомления
        test_user = User.query.filter_by(username='testuser').first()
        if test_user:
            notifications = Notification.query.filter_by(user_id=test_user.id).order_by(Notification.created_at.desc()).all()
            print(f"\n=== Уведомления для пользователя testuser ===")
            print(f"Всего уведомлений: {len(notifications)}")
            for notif in notifications:
                print(f"- [{notif.type}] {notif.message} (создано: {notif.created_at})")
        else:
            print("Тестовый пользователь не найден")

if __name__ == '__main__':
    print("=== Тестирование системы уведомлений ===\n")
    test_user, events = create_test_events()
    test_notification_system()
    print("\n=== Тестирование завершено ===")
    print(f"\nВойдите в систему как testuser / test123 чтобы увидеть уведомления")
