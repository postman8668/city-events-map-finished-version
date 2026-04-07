from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timezone, timedelta
import os
import json
from functools import wraps
from threading import Lock
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
base_dir = os.path.abspath(os.path.dirname(__file__))
instance_db_path = os.path.join(base_dir, 'instance', 'events.db')
default_db_path = os.path.join(base_dir, 'events.db')
db_uri_path = instance_db_path if os.path.exists(instance_db_path) else default_db_path
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_uri_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки для загрузки файлов
UPLOAD_FOLDER = os.path.join(base_dir, 'static', 'uploads', 'events')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Создаем папку для загрузок, если её нет
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
_init_lock = Lock()
_init_done = False
def ensure_database_seeded():
    global _init_done
    if _init_done:
        return
    with _init_lock:
        if _init_done:
            return
        try:
            db.create_all()
            total_events = Event.query.count()
            print(f"[INIT] Total events before seed: {total_events}")
            if total_events == 0:
                from datetime import time as dtime
                current_year = date.today().year
                seed_events = [
                    Event(
                        title='Экскурсия по Софийскому собору',
                        description='Историческая экскурсия по древнейшему храму Беларуси',
                        date=date(current_year, 12, 25),
                        time=dtime(11, 0),
                        location='Софийский собор, ул. Замковая, 1',
                        latitude=55.485833,
                        longitude=28.758333,
                        category='Культура',
                        interests='["история", "культура", "экскурсия", "архитектура"]',
                        price=8.0,
                        max_participants=40,
                        status='approved'
                    ),
                    Event(
                        title='Фестиваль уличной еды',
                        description='Дегустация блюд от лучших шеф-поваров Полоцка',
                        date=date(current_year, 12, 26),
                        time=dtime(12, 0),
                        location='Центральная площадь, Полоцк',
                        latitude=55.485709,
                        longitude=28.768550,
                        category='Еда',
                        interests='["еда", "фестиваль", "развлечения"]',
                        price=5.0,
                        max_participants=500,
                        status='approved'
                    ),
                    Event(
                        title='Йога в парке',
                        description='Бесплатное занятие йогой на свежем воздухе в парке',
                        date=date(current_year, 12, 27),
                        time=dtime(9, 0),
                        location='Парк культуры и отдыха, Новополоцк',
                        latitude=55.537536,
                        longitude=28.656881,
                        category='Спорт',
                        interests='["йога", "спорт", "здоровье", "природа"]',
                        price=0.0,
                        max_participants=30,
                        status='approved'
                    ),
                    Event(
                        title='Квест по городу',
                        description='Увлекательный городской квест с призами для команд',
                        date=date(current_year, 12, 28),
                        time=dtime(14, 0),
                        location='Площадь Свободы, Полоцк',
                        latitude=55.486500,
                        longitude=28.769000,
                        category='Развлечение',
                        interests='["квест", "игры", "развлечения", "команда"]',
                        price=12.0,
                        max_participants=50,
                        status='approved'
                    )
                ]
                for ev in seed_events:
                    db.session.add(ev)
                db.session.commit()
                print("[INIT] Seed events inserted")
            _init_done = True
        except Exception as e:
            print(f"[INIT] Error initializing database: {e}")

def belarus_now():
    """Возвращает текущее время по Беларуси (UTC+3)"""
    belarus_tz = timezone(timedelta(hours=3))
    return datetime.now(belarus_tz)

def allowed_file(filename):
    """Проверяет, разрешено ли расширение файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_event_image(file):
    """Сохраняет изображение события и возвращает имя файла"""
    if file and allowed_file(file.filename):
        # Генерируем уникальное имя файла
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filename
    return None

def delete_event_image(filename):
    """Удаляет изображение события"""
    if filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Ошибка при удалении файла {filename}: {e}")

@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему для доступа к этой странице.', 'warning')
            return redirect(url_for('login'))
        
        user = db.session.get(User, session.get('user_id'))
        if user and (not hasattr(user, 'is_active') or not user.is_active):
            session.clear()
            flash('Ваш аккаунт заблокирован! Обратитесь к администратору.', 'error')
            log_event('WARNING', f'Попытка доступа заблокированным пользователем: {user.username if user else "unknown"}', user.id if user else None, request)
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def log_event(level, message, user_id=None, request_obj=None):
    """Добавляет запись в лог"""
    try:
        log_entry = LogEntry(
            level=level,
            message=message,
            user_id=user_id,
            ip_address=request_obj.remote_addr if request_obj else None,
            user_agent=request_obj.headers.get('User-Agent') if request_obj else None,
            route=request_obj.endpoint if request_obj else None,
            method=request_obj.method if request_obj else None,
            timestamp=belarus_now()
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка при записи в лог: {e}")

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    interests = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, default=0.0)
    max_participants = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=belarus_now)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, approved, rejected
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    image_filename = db.Column(db.String(255), nullable=True)  # Имя файла изображения
    
    reviews = db.relationship('Review', backref='event', lazy=True, cascade='all, delete-orphan')
    saved_events = db.relationship('SavedEvent', backref='event', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', backref='created_events', foreign_keys=[creator_id])
    
    @property
    def participants_count(self):
        """Количество участников (сохраненных событий)"""
        return len(self.saved_events)
    
    @property
    def participants_percentage(self):
        """Процент заполненности события"""
        if not self.max_participants:
            return 0
        return min(100, (self.participants_count / self.max_participants) * 100)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    interests = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=belarus_now)
    
    reviews = db.relationship('Review', backref='user', lazy=True, cascade='all, delete-orphan')
    saved_events = db.relationship('SavedEvent', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=belarus_now)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)

class SavedEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    saved_at = db.Column(db.DateTime, default=belarus_now)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)

class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=belarus_now)
    level = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    route = db.Column(db.String(200), nullable=True)
    method = db.Column(db.String(10), nullable=True)

@app.context_processor
def inject_pending_count():
    """Добавляет количество событий на модерации во все шаблоны"""
    pending_count = 0
    if session.get('user_id'):
        user = db.session.get(User, session.get('user_id'))
        if user and user.username == 'admin':
            pending_count = Event.query.filter_by(status='pending').count()
    return dict(pending_events_count=pending_count)

@app.route('/')
def index():
    ensure_database_seeded()
    all_events = Event.query.filter_by(status='approved').all()

    events = Event.query.filter_by(status='approved').order_by(Event.date, Event.time).all()

    # Получаем список ID событий, в которых участвует текущий пользователь
    user_id = session.get('user_id')
    user_event_ids = set()
    if user_id:
        saved_events = SavedEvent.query.filter_by(user_id=user_id).all()
        user_event_ids = {se.event_id for se in saved_events}

    events_data = []
    for event in events:
        events_data.append({
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'date': event.date.strftime('%Y-%m-%d'),
            'time': event.time.strftime('%H:%M'),
            'location': event.location,
            'latitude': float(event.latitude) if event.latitude else 0,
            'longitude': float(event.longitude) if event.longitude else 0,
            'category': event.category,
            'interests': event.interests,
            'price': float(event.price) if event.price else 0,
            'max_participants': event.max_participants
        })
    
    categories = db.session.query(Event.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    # Получаем все уникальные интересы из всех событий
    all_interests = {}
    for event in all_events:
        try:
            interests = json.loads(event.interests)
            if isinstance(interests, list):
                for interest in interests:
                    interest_lower = interest.lower()
                    if interest_lower not in all_interests:
                        all_interests[interest_lower] = interest
        except:
            pass
    interests = sorted(list(all_interests.values()), key=str.lower)
    
    print(f"Total events in database: {len(all_events)}")
    print(f"Events loaded on index: {len(events)}")
    print(f"Categories: {categories}")
    print(f"Interests: {interests}")
    
    for i, event in enumerate(events[:3]):
        print(f"  Event {i+1}: {event.title} - lat: {event.latitude}, lng: {event.longitude}")
    
    log_event('INFO', f'Посещение главной страницы. Событий: {len(events)}, категорий: {len(categories)}', 
              user_id, request)
    
    # Передаем текущую дату в шаблон
    today = date.today()
    
    # Создаем словарь с информацией о заполненности событий
    event_full_status = {}
    for event in events:
        if event.max_participants:
            current_participants = SavedEvent.query.filter_by(event_id=event.id).count()
            event_full_status[event.id] = current_participants >= event.max_participants
        else:
            event_full_status[event.id] = False
    
    return render_template('index.html', events=events, categories=categories, interests=interests, events_json=events_data, today=today, user_event_ids=user_event_ids, event_full_status=event_full_status)

@app.route('/api/events')
def api_events():
    try:
        ensure_database_seeded()
        category = request.args.get('category')
        interest = request.args.get('interest')
        search = request.args.get('search')
        
        print(f"API called with category: '{category}', interest: '{interest}', search: '{search}'")
        
        total_events = Event.query.filter_by(status='approved').count()
        print(f"Total events in database: {total_events}")
        
        if total_events == 0:
            print("No events found in database!")
            return jsonify([])
        
        events = Event.query.filter_by(status='approved').order_by(Event.date, Event.time).all()
        
        filtered_events = []
        for event in events:
            match = True
            
            if category and category != 'all':
                if event.category != category:
                    match = False
            
            if interest and match:
                try:
                    event_interests = json.loads(event.interests)
                    if interest not in event_interests:
                        match = False
                except:
                    match = False
            
            if search and match:
                search_lower = search.lower()
                if not (search_lower in event.title.lower() or 
                        search_lower in event.description.lower() or 
                        search_lower in event.location.lower()):
                    match = False
            
            if match:
                filtered_events.append(event)
        
        events = filtered_events
        print(f"Found {len(events)} events after filtering")
        
        for event in events:
            print(f"  - {event.title} (category: {event.category})")
        
        user_id = session.get('user_id')
        user_event_ids = set()
        if user_id:
            saved_events = SavedEvent.query.filter_by(user_id=user_id).all()
            user_event_ids = {se.event_id for se in saved_events}
        
        events_data = []
        today = date.today()
        for event in events:
            is_past = event.date < today
            is_participant = event.id in user_event_ids
            
            is_full = False
            if event.max_participants:
                current_participants = SavedEvent.query.filter_by(event_id=event.id).count()
                is_full = current_participants >= event.max_participants
            
            events_data.append({
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'date': event.date.strftime('%Y-%m-%d'),
                'time': event.time.strftime('%H:%M'),
                'location': event.location,
                'latitude': float(event.latitude) if event.latitude else 0,
                'longitude': float(event.longitude) if event.longitude else 0,
                'category': event.category,
                'interests': event.interests,
                'price': float(event.price) if event.price else 0,
                'max_participants': event.max_participants,
                'is_past': is_past,
                'is_participant': is_participant,
                'is_full': is_full,
                'creator_id': event.creator_id,
                'is_my_event': event.creator_id == user_id if user_id else False
            })
        
        return jsonify(events_data)
    except Exception as e:
        print(f"Error in api_events: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    reviews = Review.query.filter_by(event_id=event_id).order_by(Review.created_at.desc()).all()
    
    avg_rating = 0
    if reviews:
        avg_rating = sum(review.rating for review in reviews) / len(reviews)
    
    # Проверяем участие пользователя в событии
    is_participant = False
    if session.get('user_id'):
        is_participant = SavedEvent.query.filter_by(
            user_id=session['user_id'],
            event_id=event_id
        ).first() is not None
    
    # Проверяем, заполнено ли событие
    is_full = False
    if event.max_participants:
        current_participants = SavedEvent.query.filter_by(event_id=event_id).count()
        is_full = current_participants >= event.max_participants
    
    # Проверяем, есть ли уже отзыв от текущего пользователя
    user_review = None
    if session.get('user_id'):
        user_review = Review.query.filter_by(
            user_id=session['user_id'],
            event_id=event_id
        ).first()
    
    return render_template('event_detail.html', event=event, reviews=reviews, avg_rating=avg_rating, is_participant=is_participant, user_review=user_review, is_full=is_full)

@app.route('/add_review', methods=['POST'])
@login_required
def add_review():
    data = request.get_json()
    
    existing_review = Review.query.filter_by(
        user_id=session['user_id'], 
        event_id=data['event_id']
    ).first()
    
    if existing_review:
        return jsonify({'success': False, 'message': 'Вы уже оставили отзыв на это событие!'})
    
    review = Review(
        rating=data['rating'],
        comment=data['comment'],
        user_id=session['user_id'],
        event_id=data['event_id']
    )
    
    db.session.add(review)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Отзыв добавлен!'})

@app.route('/review/<int:review_id>/edit', methods=['POST'])
@login_required
def edit_review(review_id):
    """Редактирование отзыва"""
    review = Review.query.get_or_404(review_id)
    user = db.session.get(User, session['user_id'])
    
    if review.user_id != user.id and user.username != 'admin':
        return jsonify({'success': False, 'message': 'У вас нет прав для редактирования этого отзыва!'}), 403
    
    data = request.get_json()
    
    try:
        review.rating = data.get('rating', review.rating)
        review.comment = data.get('comment', review.comment)
        
        db.session.commit()
        
        log_event('INFO', f'Пользователь {user.username} отредактировал отзыв {review_id}', user.id, request)
        return jsonify({'success': True, 'message': 'Отзыв обновлен!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка при обновлении отзыва: {str(e)}'}), 500

@app.route('/review/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    """Удаление отзыва"""
    review = Review.query.get_or_404(review_id)
    user = db.session.get(User, session['user_id'])
    
    if review.user_id != user.id and user.username != 'admin':
        return jsonify({'success': False, 'message': 'У вас нет прав для удаления этого отзыва!'}), 403
    
    event_id = review.event_id
    
    try:
        db.session.delete(review)
        db.session.commit()
        
        log_event('INFO', f'Пользователь {user.username} удалил отзыв {review_id}', user.id, request)
        return jsonify({'success': True, 'message': 'Отзыв удален!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка при удалении отзыва: {str(e)}'}), 500

@app.route('/save_event', methods=['POST'])
@login_required
def save_event():
    data = request.get_json()
    
    # Проверяем, не прошло ли событие
    event = Event.query.get(data['event_id'])
    if event and event.date < date.today():
        return jsonify({'success': False, 'message': 'Нельзя присоединиться к прошедшему событию!'})
    
    existing = SavedEvent.query.filter_by(user_id=session['user_id'], event_id=data['event_id']).first()
    if existing:
        return jsonify({'success': False, 'message': 'Вы уже присоединились к этому событию!'})
    
    # Проверяем лимит участников
    if event and event.max_participants:
        current_participants = SavedEvent.query.filter_by(event_id=data['event_id']).count()
        if current_participants >= event.max_participants:
            return jsonify({'success': False, 'message': 'К сожалению, все места на это событие уже заняты!'})
    
    saved_event = SavedEvent(user_id=session['user_id'], event_id=data['event_id'])
    db.session.add(saved_event)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Вы успешно присоединились к событию!'})

@app.route('/unsave_event', methods=['POST'])
@login_required
def unsave_event():
    """Отказ от участия в событии"""
    data = request.get_json()
    event_id = data.get('event_id')
    
    saved_event = SavedEvent.query.filter_by(
        user_id=session['user_id'], 
        event_id=event_id
    ).first()
    
    if not saved_event:
        return jsonify({'success': False, 'message': 'Вы не участвуете в этом событии!'})
    
    try:
        db.session.delete(saved_event)
        db.session.commit()
        
        log_event('INFO', f'Пользователь {session.get("username")} отказался от участия в событии {event_id}', session['user_id'], request)
        return jsonify({'success': True, 'message': 'Вы отказались от участия в событии!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка при отказе от участия: {str(e)}'}), 500

@app.route('/saved_events/<username>')
@login_required
def saved_events(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('Пользователь не найден!')
        return redirect(url_for('index'))
    
    if user.id != session['user_id']:
        flash('У вас нет доступа к этим событиям!')
        return redirect(url_for('index'))
    
    saved_events = SavedEvent.query.filter_by(user_id=user.id).order_by(SavedEvent.saved_at.desc()).all()
    events = [saved.event for saved in saved_events]
    
    return render_template('saved_events.html', events=events, username=username)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Сохраняем данные для возврата в форму
        form_data = {
            'username': username,
            'email': email
        }
        
        # Валидация
        errors = []
        
        if not username or len(username) < 3:
            errors.append('Имя пользователя должно содержать минимум 3 символа')
        
        if len(username) > 50:
            errors.append('Имя пользователя не должно превышать 50 символов')
        
        if not email or '@' not in email:
            errors.append('Введите корректный email адрес')
        
        if len(email) > 100:
            errors.append('Email не должен превышать 100 символов')
        
        if not password or len(password) < 6:
            errors.append('Пароль должен содержать минимум 6 символов')
        
        if len(password) > 100:
            errors.append('Пароль не должен превышать 100 символов')
        
        if password != confirm_password:
            errors.append('Пароли не совпадают')
        
        if User.query.filter_by(username=username).first():
            errors.append('Пользователь с таким именем уже существует')
        
        if User.query.filter_by(email=email).first():
            errors.append('Пользователь с таким email уже существует')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            log_event('WARNING', f'Ошибка регистрации: {username} - {", ".join(errors)}', None, request)
            return render_template('register.html', form_data=form_data)
        
        user = User(username=username, email=email, is_active=True)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация прошла успешно! Теперь вы можете войти в систему.', 'success')
        log_event('INFO', f'Новый пользователь зарегистрирован: {username} ({email})', user.id, request)
        return redirect(url_for('login'))
    
    return render_template('register.html', form_data=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Сохраняем username для возврата в форму
        form_data = {'username': username}
        
        # Валидация
        if not username:
            flash('Введите имя пользователя', 'error')
            return render_template('login.html', form_data=form_data)
        
        if not password:
            flash('Введите пароль', 'error')
            return render_template('login.html', form_data=form_data)
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not hasattr(user, 'is_active') or user.is_active is None:
                user.is_active = True
                try:
                    db.session.commit()
                except:
                    db.session.rollback()
            
            if not user.is_active:
                flash('Ваш аккаунт заблокирован! Обратитесь к администратору.', 'error')
                log_event('WARNING', f'Попытка входа заблокированным пользователем: {username}', user.id, request)
                return render_template('login.html', form_data=form_data)
            
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Добро пожаловать, {user.username}!', 'success')
            log_event('INFO', f'Успешный вход пользователя: {username}', user.id, request)
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль!', 'error')
            log_event('WARNING', f'Неудачная попытка входа: {username}', None, request)
            return render_template('login.html', form_data=form_data)
    
    return render_template('login.html', form_data=None)

@app.route('/logout')
def logout():
    username = session.get('username', 'Неизвестный')
    session.clear()
    flash('Вы успешно вышли из системы.', 'info')
    log_event('INFO', f'Выход пользователя: {username}', None, request)
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    user = db.session.get(User, session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/profile/delete', methods=['POST'])
@login_required
def delete_own_account():
    """Удаление своего аккаунта"""
    user = db.session.get(User, session['user_id'])
    
    if user.username == 'admin':
        flash('Администратор не может удалить свой аккаунт через этот интерфейс!', 'error')
        return redirect(url_for('profile'))
    
    username = user.username
    user_id = user.id
    
    try:
        db.session.delete(user)
        db.session.commit()
        
        session.clear()
        flash('Ваш аккаунт успешно удален. Все ваши данные были удалены.', 'info')
        log_event('INFO', f'Пользователь {username} удалил свой аккаунт', None, request)
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении аккаунта: {str(e)}', 'error')
        log_event('ERROR', f'Ошибка удаления аккаунта пользователем {username}: {str(e)}', user_id, request)
        return redirect(url_for('profile'))

@app.route('/test_coords')
def test_coords():
    """Тестовый маршрут для проверки координат"""
    events = Event.query.all()
    result = []
    for event in events:
        result.append({
            'title': event.title,
            'location': event.location,
            'latitude': event.latitude,
            'longitude': event.longitude
        })
    return jsonify(result)

@app.route('/admin')
@login_required
def admin_dashboard():
    """Админ-панель"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        flash('У вас нет прав для доступа к админ-панели!', 'error')
        return redirect(url_for('index'))
    
    total_events = Event.query.count()
    pending_events = Event.query.filter_by(status='pending').count()
    total_users = User.query.count()
    total_logs = LogEntry.query.count()
    
    recent_events = Event.query.order_by(Event.created_at.desc()).limit(5).all()
    
    recent_logs = LogEntry.query.order_by(LogEntry.timestamp.desc()).limit(10).all()
    
    log_event('INFO', f'Админ {user.username} зашел в админ-панель', user.id, request)
    
    return render_template('admin_dashboard.html', 
                         total_events=total_events,
                         pending_events=pending_events,
                         total_users=total_users,
                         total_logs=total_logs,
                         recent_events=recent_events,
                         recent_logs=recent_logs)

@app.route('/admin/logs')
@login_required
def view_logs():
    """Просмотр логов системы"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        flash('У вас нет прав для просмотра логов!', 'error')
        return redirect(url_for('index'))
    
    level = request.args.get('level', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    query = LogEntry.query
    
    if level != 'all':
        query = query.filter(LogEntry.level == level)
    
    logs = query.order_by(LogEntry.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    levels = db.session.query(LogEntry.level).distinct().all()
    levels = [level[0] for level in levels]
    
    log_event('INFO', f'Просмотр логов пользователем {user.username}', user.id, request)
    
    return render_template('logs.html', logs=logs, levels=levels, current_level=level)

@app.route('/admin/users')
@login_required
def admin_users():
    """Управление пользователями"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        flash('У вас нет прав для управления пользователями!', 'error')
        return redirect(url_for('index'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    
    for u in users:
        if not hasattr(u, 'is_active') or u.is_active is None:
            u.is_active = True
            try:
                db.session.commit()
            except:
                db.session.rollback()
    
    log_event('INFO', f'Админ {user.username} просматривает список пользователей', user.id, request)
    
    return render_template('admin_users.html', users=users)

@app.route('/admin/events')
@login_required
def admin_events():
    """Управление событиями и модерация"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        flash('У вас нет прав для управления событиями!', 'error')
        return redirect(url_for('index'))
    
    status_filter = request.args.get('status', 'all')
    
    if status_filter == 'all':
        events = Event.query.order_by(Event.created_at.desc()).all()
    else:
        events = Event.query.filter_by(status=status_filter).order_by(Event.created_at.desc()).all()
    
    pending_count = Event.query.filter_by(status='pending').count()
    
    log_event('INFO', f'Админ {user.username} просматривает список событий (фильтр: {status_filter})', user.id, request)
    
    return render_template('admin_events.html', events=events, status_filter=status_filter, pending_count=pending_count)

@app.route('/events/create', methods=['GET', 'POST'])
@login_required
def create_event():
    """Создание нового события любым авторизованным пользователем"""
    user = db.session.get(User, session['user_id'])
    
    if request.method == 'POST':
        try:
            # Обработка интересов: преобразуем слова через запятую в JSON массив
            interests_input = request.form.get('interests', '').strip()
            if interests_input:
                interests_list = [interest.strip().lower() for interest in interests_input.split(',') if interest.strip()]
                interests_json = json.dumps(interests_list, ensure_ascii=False)
            else:
                interests_json = '[]'
            
            form_data = {
                'title': request.form.get('title', '').strip(),
                'description': request.form.get('description', '').strip(),
                'location': request.form.get('location', '').strip(),
                'latitude': request.form.get('latitude', ''),
                'longitude': request.form.get('longitude', ''),
                'category': request.form.get('category', ''),
                'interests': interests_json,
                'price': request.form.get('price', '0'),
                'max_participants': request.form.get('max_participants', '')
            }
            
            validation_errors = validate_event_data(form_data)
            if validation_errors:
                for error in validation_errors:
                    flash(error, 'error')
                categories = db.session.query(Event.category).distinct().all()
                categories = [cat[0] for cat in categories]
                form_data['date'] = request.form.get('date', '')
                form_data['time'] = request.form.get('time', '')
                form_data['interests_display'] = interests_input
                return render_template('create_event.html', categories=categories, form_data=form_data)
            
            # Проверка на дубликаты
            event_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            event_time = datetime.strptime(request.form['time'], '%H:%M').time()
            duplicate = Event.query.filter_by(
                title=form_data['title'],
                date=event_date,
                time=event_time,
                location=form_data['location']
            ).first()
            
            if duplicate:
                flash('Событие с таким названием, датой, временем и местом уже существует!', 'error')
                categories = db.session.query(Event.category).distinct().all()
                categories = [cat[0] for cat in categories]
                form_data['date'] = request.form.get('date', '')
                form_data['time'] = request.form.get('time', '')
                form_data['interests_display'] = interests_input
                return render_template('create_event.html', categories=categories, form_data=form_data)
            
            # Админ создает события сразу одобренными, остальные - на модерации
            status = 'approved' if user.username == 'admin' else 'pending'
            
            # Обработка загрузки изображения
            image_filename = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    image_filename = save_event_image(file)
                    if not image_filename:
                        flash('Неподдерживаемый формат изображения. Разрешены: PNG, JPG, JPEG, GIF, WEBP', 'warning')
            
            event = Event(
                title=form_data['title'],
                description=form_data['description'],
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
                time=datetime.strptime(request.form['time'], '%H:%M').time(),
                location=form_data['location'],
                latitude=float(form_data['latitude']),
                longitude=float(form_data['longitude']),
                category=form_data['category'],
                interests=form_data['interests'],
                price=float(form_data['price']),
                max_participants=int(form_data['max_participants']) if form_data['max_participants'] else None,
                status=status,
                creator_id=user.id,
                image_filename=image_filename
            )
            
            db.session.add(event)
            db.session.commit()
            
            if status == 'approved':
                flash('Событие успешно создано и опубликовано!', 'success')
            else:
                flash('Событие отправлено на модерацию. После проверки администратором оно будет опубликовано.', 'info')
            
            log_event('INFO', f'Пользователь {user.username} создал событие: {form_data["title"]} (статус: {status})', user.id, request)
            return redirect(url_for('my_events'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании события: {str(e)}', 'error')
            log_event('ERROR', f'Ошибка создания события пользователем {user.username}: {str(e)}', user.id, request)
    
    categories = db.session.query(Event.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    return render_template('create_event.html', categories=categories)
    categories = [cat[0] for cat in categories]
    
    return render_template('create_event.html', categories=categories)

@app.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    """Редактирование события"""
    user = db.session.get(User, session['user_id'])
    event = Event.query.get_or_404(event_id)
    
    # Проверка прав: админ может редактировать все, пользователь - только свои
    if user.username != 'admin' and event.creator_id != user.id:
        flash('У вас нет прав для редактирования этого события!', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Обработка интересов: преобразуем слова через запятую в JSON массив
            interests_input = request.form.get('interests', '').strip()
            if interests_input:
                interests_list = [interest.strip().lower() for interest in interests_input.split(',') if interest.strip()]
                interests_json = json.dumps(interests_list, ensure_ascii=False)
            else:
                interests_json = '[]'
            
            form_data = {
                'title': request.form.get('title', '').strip(),
                'description': request.form.get('description', '').strip(),
                'location': request.form.get('location', '').strip(),
                'latitude': request.form.get('latitude', ''),
                'longitude': request.form.get('longitude', ''),
                'category': request.form.get('category', ''),
                'interests': interests_json,
                'price': request.form.get('price', '0'),
                'max_participants': request.form.get('max_participants', ''),
                'date': request.form.get('date', ''),
                'time': request.form.get('time', ''),
                'interests_display': interests_input
            }
            
            validation_errors = validate_event_data(form_data)
            if validation_errors:
                for error in validation_errors:
                    flash(error, 'error')
                categories = db.session.query(Event.category).distinct().all()
                categories = [cat[0] for cat in categories]
                # Создаем временный объект для передачи в шаблон
                temp_event = type('obj', (object,), {
                    'id': event.id,
                    'title': form_data['title'],
                    'description': form_data['description'],
                    'location': form_data['location'],
                    'latitude': form_data['latitude'],
                    'longitude': form_data['longitude'],
                    'category': form_data['category'],
                    'price': form_data['price'],
                    'max_participants': form_data['max_participants'],
                    'date': datetime.strptime(form_data['date'], '%Y-%m-%d').date() if form_data['date'] else event.date,
                    'time': datetime.strptime(form_data['time'], '%H:%M').time() if form_data['time'] else event.time
                })()
                return render_template('edit_event.html', event=temp_event, categories=categories, interests_display=form_data['interests_display'])
            
            # Проверяем были ли изменения (включая изображение)
            image_changed = False
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    image_changed = True
            
            has_changes = (
                event.title != form_data['title'] or
                event.description != form_data['description'] or
                event.date != datetime.strptime(form_data['date'], '%Y-%m-%d').date() or
                event.time != datetime.strptime(form_data['time'], '%H:%M').time() or
                event.location != form_data['location'] or
                float(event.latitude) != float(form_data['latitude']) or
                float(event.longitude) != float(form_data['longitude']) or
                event.category != form_data['category'] or
                event.interests != form_data['interests'] or
                float(event.price or 0) != float(form_data['price'] or 0) or
                (event.max_participants or 0) != (int(form_data['max_participants']) if form_data['max_participants'] else 0) or
                image_changed or
                ('remove_image' in request.form and event.image_filename)
            )
            
            if not has_changes:
                # Просто возвращаемся без уведомления
                if user.username == 'admin':
                    return redirect(url_for('admin_events'))
                else:
                    return redirect(url_for('my_events'))
            
            # Обработка изображения
            if 'remove_image' in request.form and event.image_filename:
                # Удаляем старое изображение
                delete_event_image(event.image_filename)
                event.image_filename = None
            elif 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    # Удаляем старое изображение, если есть
                    if event.image_filename:
                        delete_event_image(event.image_filename)
                    # Сохраняем новое
                    new_image = save_event_image(file)
                    if new_image:
                        event.image_filename = new_image
                    else:
                        flash('Неподдерживаемый формат изображения. Разрешены: PNG, JPG, JPEG, GIF, WEBP', 'warning')
            
            event.title = form_data['title']
            event.description = form_data['description']
            event.date = datetime.strptime(form_data['date'], '%Y-%m-%d').date()
            event.time = datetime.strptime(form_data['time'], '%H:%M').time()
            event.location = form_data['location']
            event.latitude = float(form_data['latitude'])
            event.longitude = float(form_data['longitude'])
            event.category = form_data['category']
            event.interests = form_data['interests']
            event.price = float(form_data['price']) if form_data['price'] else 0.0
            
            # Обработка изменения количества участников
            new_max_participants = int(form_data['max_participants']) if form_data['max_participants'] else None
            old_max_participants = event.max_participants
            
            event.max_participants = new_max_participants
            
            # Если уменьшили лимит участников, удаляем лишних
            if new_max_participants is not None:
                current_participants = SavedEvent.query.filter_by(event_id=event.id).order_by(SavedEvent.saved_at).all()
                if len(current_participants) > new_max_participants:
                    # Удаляем последних присоединившихся (превышающих лимит)
                    excess_participants = current_participants[new_max_participants:]
                    removed_count = 0
                    for participant in excess_participants:
                        db.session.delete(participant)
                        removed_count += 1
                    
                    if removed_count > 0:
                        flash(f'Внимание: из-за уменьшения лимита участников было удалено {removed_count} последних присоединившихся участников.', 'warning')
                        log_event('WARNING', f'При редактировании события {event.title} удалено {removed_count} участников из-за уменьшения лимита', user.id, request)
            
            # Если редактирует обычный пользователь - отправляем на модерацию
            if user.username != 'admin':
                event.status = 'pending'
                flash('Изменения отправлены на модерацию. После проверки администратором они будут опубликованы.', 'info')
                log_event('INFO', f'Пользователь {user.username} отредактировал событие: {event.title} (отправлено на модерацию)', user.id, request)
            else:
                flash('Событие успешно обновлено!', 'success')
                log_event('INFO', f'Администратор {user.username} обновил событие: {event.title}', user.id, request)
            
            db.session.commit()
            
            if user.username == 'admin':
                return redirect(url_for('admin_events'))
            else:
                return redirect(url_for('my_events'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении события: {str(e)}', 'error')
            log_event('ERROR', f'Ошибка обновления события пользователем {user.username}: {str(e)}', user.id, request)
    
    categories = db.session.query(Event.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    # Преобразуем JSON интересов обратно в строку через запятую для отображения
    interests_display = ''
    try:
        interests_list = json.loads(event.interests)
        if isinstance(interests_list, list):
            interests_display = ', '.join(interests_list)
    except:
        interests_display = ''
    
    return render_template('edit_event.html', event=event, categories=categories, interests_display=interests_display)

@app.route('/admin/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    """Удаление события"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        flash('У вас нет прав для удаления событий!', 'error')
        return redirect(url_for('index'))
    
    event = Event.query.get_or_404(event_id)
    event_title = event.title
    event_image = event.image_filename
    
    try:
        db.session.delete(event)
        db.session.commit()
        
        # Удаляем изображение, если оно есть
        if event_image:
            delete_event_image(event_image)
        
        flash('Событие успешно удалено!', 'success')
        log_event('INFO', f'Админ {user.username} удалил событие: {event_title}', user.id, request)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении события: {str(e)}', 'error')
        log_event('ERROR', f'Ошибка удаления события админом {user.username}: {str(e)}', user.id, request)
    
    return redirect(url_for('admin_events'))

@app.route('/admin/events/<int:event_id>/approve', methods=['POST'])
@login_required
def approve_event(event_id):
    """Одобрение события"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        return jsonify({'success': False, 'message': 'У вас нет прав для модерации событий!'}), 403
    
    event = Event.query.get_or_404(event_id)
    
    try:
        event.status = 'approved'
        db.session.commit()
        
        log_event('INFO', f'Админ {user.username} одобрил событие: {event.title}', user.id, request)
        return jsonify({'success': True, 'message': 'Событие одобрено и опубликовано!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500

@app.route('/admin/events/<int:event_id>/reject', methods=['POST'])
@login_required
def reject_event(event_id):
    """Отклонение события"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        return jsonify({'success': False, 'message': 'У вас нет прав для модерации событий!'}), 403
    
    event = Event.query.get_or_404(event_id)
    
    try:
        event.status = 'rejected'
        db.session.commit()
        
        log_event('INFO', f'Админ {user.username} отклонил событие: {event.title}', user.id, request)
        return jsonify({'success': True, 'message': 'Событие отклонено!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'}), 500

@app.route('/my-events')
@login_required
def my_events():
    """Просмотр своих созданных событий"""
    user = db.session.get(User, session['user_id'])
    events = Event.query.filter_by(creator_id=user.id).order_by(Event.created_at.desc()).all()
    
    log_event('INFO', f'Пользователь {user.username} просматривает свои события', user.id, request)
    
    return render_template('my_events.html', events=events)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Удаление пользователя"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        flash('У вас нет прав для удаления пользователей!', 'error')
        return redirect(url_for('index'))
    
    if user_id == user.id:
        flash('Нельзя удалить самого себя!', 'error')
        return redirect(url_for('admin_users'))
    
    target_user = User.query.get_or_404(user_id)
    username = target_user.username
    
    try:
        db.session.delete(target_user)
        db.session.commit()
        
        flash('Пользователь успешно удален!', 'success')
        log_event('INFO', f'Админ {user.username} удалил пользователя: {username}', user.id, request)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении пользователя: {str(e)}', 'error')
        log_event('ERROR', f'Ошибка удаления пользователя админом {user.username}: {str(e)}', user.id, request)
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>')
@login_required
def view_user_details(user_id):
    """Просмотр детальной информации о пользователе"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        flash('У вас нет прав для просмотра информации о пользователях!', 'error')
        return redirect(url_for('index'))
    
    target_user = User.query.get_or_404(user_id)
    
    reviews_count = Review.query.filter_by(user_id=user_id).count()
    saved_events_count = SavedEvent.query.filter_by(user_id=user_id).count()
    logs_count = LogEntry.query.filter_by(user_id=user_id).count()
    
    recent_reviews = Review.query.filter_by(user_id=user_id).order_by(Review.created_at.desc()).limit(5).all()
    
    recent_saved_events = SavedEvent.query.filter_by(user_id=user_id).order_by(SavedEvent.saved_at.desc()).limit(5).all()
    
    log_event('INFO', f'Админ {user.username} просматривает детали пользователя: {target_user.username}', user.id, request)
    
    return render_template('user_details.html', 
                         target_user=target_user,
                         reviews_count=reviews_count,
                         saved_events_count=saved_events_count,
                         logs_count=logs_count,
                         recent_reviews=recent_reviews,
                         recent_saved_events=recent_saved_events)

@app.route('/admin/users/<int:user_id>/toggle_status', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    """Переключение статуса пользователя (активен/заблокирован)"""
    user = db.session.get(User, session['user_id'])
    if user.username != 'admin':
        flash('У вас нет прав для изменения статуса пользователей!', 'error')
        return redirect(url_for('index'))
    
    if user_id == user.id:
        flash('Нельзя изменить статус самого себя!', 'error')
        return redirect(url_for('admin_users'))
    
    target_user = User.query.get_or_404(user_id)
    
    if not hasattr(target_user, 'is_active') or target_user.is_active is None:
        target_user.is_active = True
    
    target_user.is_active = not target_user.is_active
    status = "активирован" if target_user.is_active else "заблокирован"
    
    try:
        db.session.commit()
        
        flash(f'Пользователь {target_user.username} {status}!', 'success')
        log_event('INFO', f'Админ {user.username} {status} пользователя: {target_user.username}', user.id, request)
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при изменении статуса пользователя: {str(e)}', 'error')
        log_event('ERROR', f'Ошибка изменения статуса пользователя админом {user.username}: {str(e)}', user.id, request)
    
    return redirect(url_for('admin_users'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

def validate_event_data(data):
    """Валидация данных события"""
    errors = []
    
    if not data.get('title') or len(data['title'].strip()) < 3:
        errors.append('Название события должно содержать минимум 3 символа')
    
    if len(data.get('title', '').strip()) > 200:
        errors.append('Название события не должно превышать 200 символов')
    
    if not data.get('description') or len(data['description'].strip()) < 10:
        errors.append('Описание должно содержать минимум 10 символов')
    
    if len(data.get('description', '').strip()) > 5000:
        errors.append('Описание не должно превышать 5000 символов')
    
    if not data.get('location') or len(data['location'].strip()) < 3:
        errors.append('Место проведения должно содержать минимум 3 символа')
    
    if len(data.get('location', '').strip()) > 500:
        errors.append('Место проведения не должно превышать 500 символов')
    
    try:
        lat = float(data.get('latitude', 0))
        lng = float(data.get('longitude', 0))
        if not (-90 <= lat <= 90):
            errors.append('Широта должна быть от -90 до 90')
        if not (-180 <= lng <= 180):
            errors.append('Долгота должна быть от -180 до 180')
    except (ValueError, TypeError):
        errors.append('Координаты должны быть числами')
    
    try:
        price = float(data.get('price', 0))
        if price < 0:
            errors.append('Цена не может быть отрицательной')
        if price > 999999:
            errors.append('Цена не может превышать 999999 BYN')
    except (ValueError, TypeError):
        errors.append('Цена должна быть числом')
    
    try:
        if data.get('max_participants'):
            max_participants = int(data.get('max_participants'))
            if max_participants < 1:
                errors.append('Максимальное количество участников должно быть больше 0')
            if max_participants > 100000:
                errors.append('Максимальное количество участников не может превышать 100000')
    except (ValueError, TypeError):
        if data.get('max_participants'):
            errors.append('Максимальное количество участников должно быть целым числом')
    
    try:
        interests = json.loads(data.get('interests', '[]'))
        if not isinstance(interests, list):
            errors.append('Интересы должны быть массивом')
        elif len(interests) == 0:
            errors.append('Необходимо указать хотя бы один интерес')
        elif len(interests) > 20:
            errors.append('Максимум 20 интересов')
    except json.JSONDecodeError:
        errors.append('Интересы должны быть в формате JSON массива')
    
    return errors

@app.route('/dev/update_dates')
def update_event_dates():
    """Обновление дат всех существующих событий на конец декабря"""
    try:
        current_year = date.today().year
        all_events = Event.query.order_by(Event.id).all()
        
        if not all_events:
            return jsonify({'success': False, 'message': 'В базе нет событий для обновления'}), 400
        
        december_days = [25, 26, 27, 28, 29, 30, 31]
        updated_count = 0
        
        for i, event in enumerate(all_events):
            day = december_days[i % len(december_days)]
            event.date = date(current_year, 12, day)
            updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'updated': updated_count,
            'message': f'Обновлено {updated_count} событий. Даты установлены на конец декабря {current_year} года'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dev/reseed')
def dev_reseed():
    """Переинициализация БД и наполнение демо-событиями (для разработки)."""
    if request.args.get('confirm') != '1':
        return jsonify({
            'message': 'Добавьте ?confirm=1 к URL для подтверждения пересоздания БД',
            'warning': 'Осторожно: это удалит все данные'
        }), 400

    try:
        db.drop_all()
        db.create_all()

        from datetime import time as dtime
        current_year = date.today().year
        test_events = [
            Event(
                title='Экскурсия по Софийскому собору',
                description='Историческая экскурсия по древнейшему храму Беларуси',
                date=date(current_year, 12, 25),
                time=dtime(11, 0),
                location='Софийский собор, ул. Замковая, 1',
                latitude=55.485833,
                longitude=28.758333,
                category='Культура',
                interests='["история", "культура", "экскурсия", "архитектура"]',
                price=8.0,
                max_participants=40
            ),
            Event(
                title='Концерт классической музыки',
                description='Выступление симфонического оркестра в Полоцкой филармонии',
                date=date(current_year, 12, 25),
                time=dtime(19, 0),
                location='Полоцкая филармония, ул. Нижне-Покровская, 22',
                latitude=55.484051,
                longitude=28.767942,
                category='Музыка',
                interests='["классическая музыка", "культура", "искусство"]',
                price=15.0,
                max_participants=200
            ),
            Event(
                title='Лекция по истории',
                description='Лекция "История Полоцкого княжества"',
                date=date(current_year, 12, 26),
                time=dtime(17, 0),
                location='Исторический музей, ул. Нижне-Покровская, 33',
                latitude=55.485201,
                longitude=28.763162,
                category='Образование',
                interests='["история", "лекция", "образование", "культура"]',
                price=6.0,
                max_participants=60
            ),
            Event(
                title='Фестиваль уличной еды',
                description='Дегустация блюд от лучших шеф-поваров Полоцка',
                date=date(current_year, 12, 26),
                time=dtime(12, 0),
                location='Центральная площадь, Полоцк',
                latitude=55.485709,
                longitude=28.768550,
                category='Еда',
                interests='["еда", "фестиваль", "развлечения"]',
                price=5.0,
                max_participants=500
            ),
            Event(
                title='Выставка современного искусства',
                description='Работы молодых художников Полоцка и Новополоцка',
                date=date(current_year, 12, 27),
                time=dtime(14, 0),
                location='Художественная галерея, ул. Нижне-Покровская, 46',
                latitude=55.485994,
                longitude=28.766753,
                category='Искусство',
                interests='["искусство", "выставка", "культура"]',
                price=3.0,
                max_participants=50
            ),
            Event(
                title='Мастер-класс по живописи',
                description='Урок рисования акварелью для начинающих',
                date=date(current_year, 12, 27),
                time=dtime(15, 30),
                location='Детская художественная школа, ул. Евфросинии Полоцкой, 12',
                latitude=55.485581,
                longitude=28.769598,
                category='Образование',
                interests='["живопись", "творчество", "обучение", "искусство"]',
                price=12.0,
                max_participants=15
            ),
            Event(
                title='Футбольный матч',
                description='Товарищеский матч между командами Полоцка и Новополоцка',
                date=date(current_year, 12, 28),
                time=dtime(16, 0),
                location='Стадион "Спартак", ул. Спортивная, 5',
                latitude=55.488038,
                longitude=28.765588,
                category='Спорт',
                interests='["футбол", "спорт", "соревнования"]',
                price=10.0,
                max_participants=1000
            ),
            Event(
                title='Велосипедная прогулка',
                description='Групповая велопрогулка по окрестностям Полоцка',
                date=date(current_year, 12, 28),
                time=dtime(14, 30),
                location='Парк Победы, Полоцк',
                latitude=55.482748,
                longitude=28.756187,
                category='Спорт',
                interests='["велосипед", "спорт", "природа", "активный отдых"]',
                price=0.0,
                max_participants=25
            ),
            Event(
                title='Мастер-класс по программированию',
                description='Изучение Python для начинающих в IT-центре',
                date=date(current_year, 12, 29),
                time=dtime(18, 30),
                location='IT-центр, ул. Блохина, 29',
                latitude=55.537797,
                longitude=28.638198,
                category='Образование',
                interests='["программирование", "технологии", "обучение"]',
                price=20.0,
                max_participants=25
            ),
            Event(
                title='Концерт рок-музыки',
                description='Выступление местных рок-групп в молодежном центре',
                date=date(current_year, 12, 29),
                time=dtime(20, 0),
                location='Молодежный центр, ул. Молодежная, 1',
                latitude=55.530672,
                longitude=28.675113,
                category='Музыка',
                interests='["рок", "музыка", "молодежь", "концерт"]',
                price=7.0,
                max_participants=150
            ),
            Event(
                title='Йога в парке',
                description='Бесплатное занятие йогой на свежем воздухе в парке',
                date=date(current_year, 12, 30),
                time=dtime(9, 0),
                location='Парк культуры и отдыха, Новополоцк',
                latitude=55.537536,
                longitude=28.656881,
                category='Спорт',
                interests='["йога", "спорт", "здоровье", "природа"]',
                price=0.0,
                max_participants=30
            ),
            Event(
                title='Выставка фотографии',
                description='Фотовыставка "Природа Витебщины"',
                date=date(current_year, 12, 30),
                time=dtime(16, 0),
                location='Галерея современного искусства, ул. Молодежная, 45',
                latitude=55.530666,
                longitude=28.660394,
                category='Искусство',
                interests='["фотография", "природа", "выставка", "искусство"]',
                price=4.0,
                max_participants=80
            ),
            Event(
                title='Кулинарный мастер-класс',
                description='Учимся готовить традиционные белорусские блюда',
                date=date(current_year, 12, 31),
                time=dtime(13, 0),
                location='Кулинарная студия "Вкус", ул. Промышленная, 15',
                latitude=55.530041,
                longitude=28.664362,
                category='Еда',
                interests='["кулинария", "еда", "обучение", "традиции"]',
                price=18.0,
                max_participants=12
            ),
            Event(
                title='Теннисный турнир',
                description='Любительский турнир по большому теннису',
                date=date(current_year, 12, 31),
                time=dtime(10, 0),
                location='Теннисный клуб, ул. Спортивная, 3',
                latitude=55.538200,
                longitude=28.646782,
                category='Спорт',
                interests='["теннис", "спорт", "соревнования"]',
                price=15.0,
                max_participants=20
            )
        ]

        for event in test_events:
            db.session.add(event)

        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', email='admin@example.com', is_active=True)
            admin_user.set_password('admin123')
            db.session.add(admin_user)

        db.session.commit()

        total_events = Event.query.count()
        return jsonify({'success': True, 'events': total_events, 'message': 'База пересоздана и заполнена демо-данными'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        event_count = Event.query.count()
        print(f"Current events in database: {event_count}")
        
        if event_count == 0:
            admin_user = User.query.filter_by(username='admin').first()
            if admin_user:
                print("Тестовый пользователь уже существует")
            from datetime import time
            current_year = date.today().year
            
            test_events = [
                Event(
                    title='Экскурсия по Софийскому собору',
                    description='Историческая экскурсия по древнейшему храму Беларуси',
                    date=date(current_year, 12, 25),
                    time=time(11, 0),
                    location='Софийский собор, ул. Замковая, 1',
                    latitude=55.485833,
                    longitude=28.758333,
                    category='Культура',
                    interests='["история", "культура", "экскурсия", "архитектура"]',
                    price=8.0,
                    max_participants=40
                ),
                Event(
                    title='Концерт классической музыки',
                    description='Выступление симфонического оркестра в Полоцкой филармонии',
                    date=date(current_year, 12, 25),
                    time=time(19, 0),
                    location='Полоцкая филармония, ул. Нижне-Покровская, 22',
                    latitude=55.484051,
                    longitude=28.767942,
                    category='Музыка',
                    interests='["классическая музыка", "культура", "искусство"]',
                    price=15.0,
                    max_participants=200
                ),
                Event(
                    title='Лекция по истории',
                    description='Лекция "История Полоцкого княжества"',
                    date=date(current_year, 12, 26),
                    time=time(17, 0),
                    location='Исторический музей, ул. Нижне-Покровская, 33',
                    latitude=55.485201,
                    longitude=28.763162,
                    category='Образование',
                    interests='["история", "лекция", "образование", "культура"]',
                    price=6.0,
                    max_participants=60
                ),
                Event(
                    title='Фестиваль уличной еды',
                    description='Дегустация блюд от лучших шеф-поваров Полоцка',
                    date=date(current_year, 12, 26),
                    time=time(12, 0),
                    location='Центральная площадь, Полоцк',
                    latitude=55.485709,
                    longitude=28.768550,
                    category='Еда',
                    interests='["еда", "фестиваль", "развлечения"]',
                    price=5.0,
                    max_participants=500
                ),
                Event(
                    title='Выставка современного искусства',
                    description='Работы молодых художников Полоцка и Новополоцка',
                    date=date(current_year, 12, 27),
                    time=time(14, 0),
                    location='Художественная галерея, ул. Нижне-Покровская, 46',
                    latitude=55.485994,
                    longitude=28.766753,
                    category='Искусство',
                    interests='["искусство", "выставка", "культура"]',
                    price=3.0,
                    max_participants=50
                ),
                Event(
                    title='Мастер-класс по живописи',
                    description='Урок рисования акварелью для начинающих',
                    date=date(current_year, 12, 27),
                    time=time(15, 30),
                    location='Детская художественная школа, ул. Евфросинии Полоцкой, 12',
                    latitude=55.485581,
                    longitude=28.769598,
                    category='Образование',
                    interests='["живопись", "творчество", "обучение", "искусство"]',
                    price=12.0,
                    max_participants=15
                ),
                Event(
                    title='Футбольный матч',
                    description='Товарищеский матч между командами Полоцка и Новополоцка',
                    date=date(current_year, 12, 28),
                    time=time(16, 0),
                    location='Стадион "Спартак", ул. Спортивная, 5',
                    latitude=55.488038,
                    longitude=28.765588,
                    category='Спорт',
                    interests='["футбол", "спорт", "соревнования"]',
                    price=10.0,
                    max_participants=1000
                ),
                Event(
                    title='Велосипедная прогулка',
                    description='Групповая велопрогулка по окрестностям Полоцка',
                    date=date(current_year, 12, 28),
                    time=time(14, 30),
                    location='Парк Победы, Полоцк',
                    latitude=55.482748,
                    longitude=28.756187,
                    category='Спорт',
                    interests='["велосипед", "спорт", "природа", "активный отдых"]',
                    price=0.0,
                    max_participants=25
                ),
                Event(
                    title='Мастер-класс по программированию',
                    description='Изучение Python для начинающих в IT-центре',
                    date=date(current_year, 12, 29),
                    time=time(18, 30),
                    location='IT-центр, ул. Блохина, 29',
                    latitude=55.537797,
                    longitude=28.638198,
                    category='Образование',
                    interests='["программирование", "технологии", "обучение"]',
                    price=20.0,
                    max_participants=25
                ),
                Event(
                    title='Концерт рок-музыки',
                    description='Выступление местных рок-групп в молодежном центре',
                    date=date(current_year, 12, 29),
                    time=time(20, 0),
                    location='Молодежный центр, ул. Молодежная, 1',
                    latitude=55.530672,
                    longitude=28.675113,
                    category='Музыка',
                    interests='["рок", "музыка", "молодежь", "концерт"]',
                    price=7.0,
                    max_participants=150
                ),
                Event(
                    title='Йога в парке',
                    description='Бесплатное занятие йогой на свежем воздухе в парке',
                    date=date(current_year, 12, 30),
                    time=time(9, 0),
                    location='Парк культуры и отдыха, Новополоцк',
                    latitude=55.537536,
                    longitude=28.656881,
                    category='Спорт',
                    interests='["йога", "спорт", "здоровье", "природа"]',
                    price=0.0,
                    max_participants=30
                ),
                Event(
                    title='Выставка фотографии',
                    description='Фотовыставка "Природа Витебщины"',
                    date=date(current_year, 12, 30),
                    time=time(16, 0),
                    location='Галерея современного искусства, ул. Молодежная, 45',
                    latitude=55.530666,
                    longitude=28.660394,
                    category='Искусство',
                    interests='["фотография", "природа", "выставка", "искусство"]',
                    price=4.0,
                    max_participants=80
                ),
                Event(
                    title='Кулинарный мастер-класс',
                    description='Учимся готовить традиционные белорусские блюда',
                    date=date(current_year, 12, 31),
                    time=time(13, 0),
                    location='Кулинарная студия "Вкус", ул. Промышленная, 15',
                    latitude=55.530041,
                    longitude=28.664362,
                    category='Еда',
                    interests='["кулинария", "еда", "обучение", "традиции"]',
                    price=18.0,
                    max_participants=12
                ),
                Event(
                    title='Теннисный турнир',
                    description='Любительский турнир по большому теннису',
                    date=date(current_year, 12, 31),
                    time=time(10, 0),
                    location='Теннисный клуб, ул. Спортивная, 3',
                    latitude=55.538200,
                    longitude=28.646782,
                    category='Спорт',
                    interests='["теннис", "спорт", "соревнования"]',
                    price=15.0,
                    max_participants=20
                )
            ]
            
            for event in test_events:
                db.session.add(event)
            
            if not admin_user:
                test_user = User(username='admin', email='admin@example.com', is_active=True)
                test_user.set_password('admin123')
                db.session.add(test_user)
                print("Тестовый пользователь создан")
            
            db.session.commit()
            print("Тестовые данные добавлены!")
            print("Тестовый пользователь: admin / admin123")
    
    app.run(debug=True)
