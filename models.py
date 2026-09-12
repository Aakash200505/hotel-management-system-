from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user', nullable=False)
    phone = db.Column(db.String(30), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('Booking', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def bootstrap_admin():
        admin = User.query.filter_by(email='admin@hotel.com').first()
        if not admin:
            admin = User(name='Administrator', email='admin@hotel.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()


class Hotel(db.Model):
    __tablename__ = 'hotels'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    amenities = db.Column(db.Text, default='')
    price_per_night = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Float, default=4.0)
    image_filename = db.Column(db.String(255), default='default-hotel.jpg')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rooms = db.relationship('Room', backref='hotel', lazy=True, cascade='all, delete-orphan')
    bookings = db.relationship('Booking', backref='hotel', lazy=True, cascade='all, delete-orphan')


class Room(db.Model):
    __tablename__ = 'rooms'

    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    room_type = db.Column(db.String(50), nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    price_modifier = db.Column(db.Float, default=1.0)
    availability_count = db.Column(db.Integer, default=1)

    bookings = db.relationship('Booking', backref='room', lazy=True)


class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    nights = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='pending')
    payment_status = db.Column(db.String(30), default='unpaid')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payments = db.relationship('Payment', backref='booking', lazy=True, cascade='all, delete-orphan')


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(50), default='dummy_gateway')
    status = db.Column(db.String(30), nullable=False)
    transaction_ref = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
