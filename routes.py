import os
import uuid
from functools import wraps
from datetime import datetime, date
from collections import defaultdict
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from models import db, User, Hotel, Room, Booking, Payment


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('index'))
        return func(*args, **kwargs)

    return wrapper


def nights_between(check_in, check_out):
    return (check_out - check_in).days


def demand_multiplier(check_in_date):
    if check_in_date.month in [6, 7, 8, 12]:
        return 1.2
    if check_in_date.weekday() in [4, 5]:
        return 1.1
    return 1.0


def room_available(room_id, check_in, check_out):
    overlapping = (
        Booking.query.filter(
            Booking.room_id == room_id,
            Booking.status.in_(['pending', 'confirmed']),
            Booking.check_in < check_out,
            Booking.check_out > check_in,
        ).count()
    )
    room = Room.query.get(room_id)
    return room is not None and overlapping < room.availability_count


def calculate_total_price(room, check_in, check_out):
    nights = nights_between(check_in, check_out)
    multiplier = demand_multiplier(check_in)
    total = room.base_price * room.price_modifier * nights * multiplier
    return max(total, 0), nights


def save_hotel_image(upload_file):
    if not upload_file or upload_file.filename == '':
        return None
    if not allowed_file(upload_file.filename):
        return None

    extension = upload_file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{extension}"
    upload_dir = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'])
    os.makedirs(upload_dir, exist_ok=True)
    upload_file.save(os.path.join(upload_dir, secure_filename(filename)))
    return filename


def parse_date(value):
    return datetime.strptime(value, '%Y-%m-%d').date()


def init_routes(app):
    @app.route('/')
    def index():
        location = request.args.get('location', '').strip()
        min_price = request.args.get('min_price', '').strip()
        max_price = request.args.get('max_price', '').strip()
        rating = request.args.get('rating', '').strip()
        check_in_str = request.args.get('check_in', '').strip()
        check_out_str = request.args.get('check_out', '').strip()

        hotels_query = Hotel.query

        try:
            if location:
                hotels_query = hotels_query.filter(Hotel.location.ilike(f'%{location}%'))
            if min_price:
                hotels_query = hotels_query.filter(Hotel.price_per_night >= float(min_price))
            if max_price:
                hotels_query = hotels_query.filter(Hotel.price_per_night <= float(max_price))
            if rating:
                hotels_query = hotels_query.filter(Hotel.rating >= float(rating))
        except ValueError:
            flash('Price/rating filters must be numeric.', 'warning')
            return redirect(url_for('index'))

        hotels = hotels_query.order_by(Hotel.rating.desc()).all()

        if check_in_str and check_out_str:
            try:
                check_in = parse_date(check_in_str)
                check_out = parse_date(check_out_str)
                if check_out > check_in:
                    filtered = []
                    for hotel in hotels:
                        if any(room_available(room.id, check_in, check_out) for room in hotel.rooms):
                            filtered.append(hotel)
                    hotels = filtered
            except ValueError:
                flash('Invalid date format for search filters.', 'warning')

        return render_template('index.html', hotels=hotels)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            if not all([name, email, password, confirm_password]):
                flash('All fields are required.', 'danger')
                return redirect(url_for('register'))

            if password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return redirect(url_for('register'))

            if len(password) < 6:
                flash('Password must be at least 6 characters.', 'danger')
                return redirect(url_for('register'))

            if User.query.filter_by(email=email).first():
                flash('Email already registered.', 'warning')
                return redirect(url_for('register'))

            user = User(name=name, email=email, role='user')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))

        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '').strip()

            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(password):
                flash('Invalid email or password.', 'danger')
                return redirect(url_for('login'))

            login_user(user)
            flash('Login successful.', 'success')

            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))

        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Logged out successfully.', 'info')
        return redirect(url_for('index'))

    @app.route('/dashboard', methods=['GET', 'POST'])
    @login_required
    def dashboard():
        if request.method == 'POST':
            current_user.name = request.form.get('name', current_user.name).strip() or current_user.name
            current_user.phone = request.form.get('phone', current_user.phone).strip()
            db.session.commit()
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('dashboard'))

        bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
        return render_template('dashboard.html', bookings=bookings)

    @app.route('/hotel/<int:hotel_id>')
    def hotel_detail(hotel_id):
        hotel = Hotel.query.get_or_404(hotel_id)
        return render_template('hotel_detail.html', hotel=hotel)

    @app.route('/booking/<int:hotel_id>', methods=['GET', 'POST'])
    @login_required
    def booking(hotel_id):
        hotel = Hotel.query.get_or_404(hotel_id)

        if request.method == 'POST':
            room_id = int(request.form.get('room_id', 0))
            check_in_str = request.form.get('check_in', '')
            check_out_str = request.form.get('check_out', '')

            room = Room.query.filter_by(id=room_id, hotel_id=hotel.id).first()
            if not room:
                flash('Selected room type is invalid.', 'danger')
                return redirect(url_for('booking', hotel_id=hotel.id))

            try:
                check_in = parse_date(check_in_str)
                check_out = parse_date(check_out_str)
            except ValueError:
                flash('Please provide valid check-in and check-out dates.', 'danger')
                return redirect(url_for('booking', hotel_id=hotel.id))

            if check_in < date.today() or check_out <= check_in:
                flash('Invalid date range selected.', 'danger')
                return redirect(url_for('booking', hotel_id=hotel.id))

            if not room_available(room.id, check_in, check_out):
                flash('Room not available for selected dates.', 'warning')
                return redirect(url_for('booking', hotel_id=hotel.id))

            total_price, nights = calculate_total_price(room, check_in, check_out)

            booking_record = Booking(
                user_id=current_user.id,
                hotel_id=hotel.id,
                room_id=room.id,
                check_in=check_in,
                check_out=check_out,
                nights=nights,
                total_price=round(total_price, 2),
                status='pending',
                payment_status='unpaid',
            )
            db.session.add(booking_record)
            db.session.commit()

            flash('Booking created. Proceed to payment.', 'success')
            return redirect(url_for('payment', booking_id=booking_record.id))

        return render_template('booking.html', hotel=hotel)

    @app.route('/payment/<int:booking_id>', methods=['GET', 'POST'])
    @login_required
    def payment(booking_id):
        booking_record = Booking.query.get_or_404(booking_id)
        if booking_record.user_id != current_user.id and current_user.role != 'admin':
            flash('Unauthorized payment access.', 'danger')
            return redirect(url_for('index'))

        if request.method == 'POST':
            action = request.form.get('payment_action')
            transaction_ref = f'TXN-{uuid.uuid4().hex[:10].upper()}'

            if action == 'success':
                booking_record.payment_status = 'paid'
                booking_record.status = 'confirmed'
                payment_row = Payment(
                    booking_id=booking_record.id,
                    amount=booking_record.total_price,
                    method='dummy_gateway',
                    status='success',
                    transaction_ref=transaction_ref,
                )
                db.session.add(payment_row)
                db.session.commit()
                flash('Payment successful. Booking confirmed.', 'success')
                return redirect(url_for('receipt', booking_id=booking_record.id))

            booking_record.payment_status = 'failed'
            booking_record.status = 'pending'
            payment_row = Payment(
                booking_id=booking_record.id,
                amount=booking_record.total_price,
                method='dummy_gateway',
                status='failed',
                transaction_ref=transaction_ref,
            )
            db.session.add(payment_row)
            db.session.commit()
            flash('Payment failed. Please retry.', 'danger')
            return redirect(url_for('payment', booking_id=booking_record.id))

        return render_template('payment.html', booking=booking_record)

    @app.route('/receipt/<int:booking_id>')
    @login_required
    def receipt(booking_id):
        booking_record = Booking.query.get_or_404(booking_id)
        if booking_record.user_id != current_user.id and current_user.role != 'admin':
            flash('Unauthorized receipt access.', 'danger')
            return redirect(url_for('index'))

        latest_payment = (
            Payment.query.filter_by(booking_id=booking_record.id)
            .order_by(Payment.created_at.desc())
            .first()
        )
        return render_template('receipt.html', booking=booking_record, payment=latest_payment)

    @app.route('/cancel-booking/<int:booking_id>', methods=['POST'])
    @login_required
    def cancel_booking(booking_id):
        booking_record = Booking.query.get_or_404(booking_id)
        if booking_record.user_id != current_user.id and current_user.role != 'admin':
            flash('Unauthorized cancellation.', 'danger')
            return redirect(url_for('index'))

        if booking_record.status == 'cancelled':
            flash('Booking is already cancelled.', 'info')
            return redirect(url_for('dashboard'))

        booking_record.status = 'cancelled'
        db.session.commit()
        flash('Booking cancelled successfully.', 'warning')

        if current_user.role == 'admin':
            return redirect(url_for('admin_bookings'))
        return redirect(url_for('dashboard'))

    @app.route('/admin')
    @login_required
    @admin_required
    def admin_dashboard():
        total_bookings = Booking.query.count()
        confirmed_bookings = Booking.query.filter_by(status='confirmed').count()
        total_revenue = (
            db.session.query(db.func.coalesce(db.func.sum(Booking.total_price), 0))
            .filter(Booking.payment_status == 'paid')
            .scalar()
        )
        total_users = User.query.filter_by(role='user').count()

        paid_bookings = Booking.query.filter(Booking.payment_status == 'paid').all()
        monthly = defaultdict(float)
        for item in paid_bookings:
            key = item.created_at.strftime('%Y-%m')
            monthly[key] += item.total_price

        chart_labels = sorted(monthly.keys())
        chart_values = [round(monthly[key], 2) for key in chart_labels]

        return render_template(
            'admin.html',
            total_bookings=total_bookings,
            confirmed_bookings=confirmed_bookings,
            total_revenue=round(total_revenue or 0, 2),
            total_users=total_users,
            chart_labels=chart_labels,
            chart_values=chart_values,
        )

    @app.route('/admin/hotels')
    @login_required
    @admin_required
    def admin_hotels():
        hotels = Hotel.query.order_by(Hotel.created_at.desc()).all()
        return render_template('admin_hotels.html', hotels=hotels)

    @app.route('/admin/hotels/add', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_add_hotel():
        if request.method == 'POST':
            try:
                price_per_night = float(request.form.get('price_per_night', 0) or 0)
                rating = float(request.form.get('rating', 4.0) or 4.0)
            except ValueError:
                flash('Price and rating must be numeric.', 'danger')
                return redirect(url_for('admin_add_hotel'))

            hotel = Hotel(
                name=request.form.get('name', '').strip(),
                description=request.form.get('description', '').strip(),
                location=request.form.get('location', '').strip(),
                address=request.form.get('address', '').strip(),
                amenities=request.form.get('amenities', '').strip(),
                price_per_night=price_per_night,
                rating=rating,
            )

            if not all([hotel.name, hotel.description, hotel.location, hotel.address]):
                flash('Please fill all required hotel fields.', 'danger')
                return redirect(url_for('admin_add_hotel'))

            image_file = request.files.get('image')
            image_name = save_hotel_image(image_file)
            if image_name:
                hotel.image_filename = image_name

            db.session.add(hotel)
            db.session.commit()
            flash('Hotel added successfully.', 'success')
            return redirect(url_for('admin_hotels'))

        return render_template('admin_hotel_form.html', mode='add', hotel=None)

    @app.route('/admin/hotels/edit/<int:hotel_id>', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_edit_hotel(hotel_id):
        hotel = Hotel.query.get_or_404(hotel_id)

        if request.method == 'POST':
            hotel.name = request.form.get('name', hotel.name).strip()
            hotel.description = request.form.get('description', hotel.description).strip()
            hotel.location = request.form.get('location', hotel.location).strip()
            hotel.address = request.form.get('address', hotel.address).strip()
            hotel.amenities = request.form.get('amenities', hotel.amenities).strip()

            try:
                hotel.price_per_night = float(request.form.get('price_per_night', hotel.price_per_night) or hotel.price_per_night)
                hotel.rating = float(request.form.get('rating', hotel.rating) or hotel.rating)
            except ValueError:
                flash('Price and rating must be numeric.', 'danger')
                return redirect(url_for('admin_edit_hotel', hotel_id=hotel.id))

            image_file = request.files.get('image')
            image_name = save_hotel_image(image_file)
            if image_name:
                hotel.image_filename = image_name

            db.session.commit()
            flash('Hotel updated successfully.', 'success')
            return redirect(url_for('admin_hotels'))

        return render_template('admin_hotel_form.html', mode='edit', hotel=hotel)

    @app.route('/admin/hotels/delete/<int:hotel_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_hotel(hotel_id):
        hotel = Hotel.query.get_or_404(hotel_id)
        db.session.delete(hotel)
        db.session.commit()
        flash('Hotel deleted successfully.', 'warning')
        return redirect(url_for('admin_hotels'))

    @app.route('/admin/rooms')
    @login_required
    @admin_required
    def admin_rooms():
        rooms = Room.query.order_by(Room.id.desc()).all()
        hotels = Hotel.query.order_by(Hotel.name.asc()).all()
        return render_template('admin_rooms.html', rooms=rooms, hotels=hotels)

    @app.route('/admin/rooms/add', methods=['POST'])
    @login_required
    @admin_required
    def admin_add_room():
        try:
            hotel_id = int(request.form.get('hotel_id', 0))
            base_price = float(request.form.get('base_price', 0) or 0)
        except ValueError:
            flash('Invalid numeric input for room.', 'danger')
            return redirect(url_for('admin_rooms'))

        room_type = request.form.get('room_type', '').strip()

        if not Hotel.query.get(hotel_id):
            flash('Invalid hotel selected for room.', 'danger')
            return redirect(url_for('admin_rooms'))

        room = Room(
            hotel_id=hotel_id,
            room_type=room_type,
            base_price=base_price,
            price_modifier=1.0,
            availability_count=1,
        )
        db.session.add(room)
        db.session.commit()
        flash('Room added successfully.', 'success')
        return redirect(url_for('admin_rooms'))

    @app.route('/admin/rooms/edit/<int:room_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_edit_room(room_id):
        room = Room.query.get_or_404(room_id)
        room.room_type = request.form.get('room_type', room.room_type).strip()
        try:
            room.base_price = float(request.form.get('base_price', room.base_price) or room.base_price)
        except ValueError:
            flash('Invalid numeric input for room update.', 'danger')
            return redirect(url_for('admin_rooms'))

        db.session.commit()
        flash('Room updated successfully.', 'success')
        return redirect(url_for('admin_rooms'))

    @app.route('/admin/rooms/delete/<int:room_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_delete_room(room_id):
        room = Room.query.get_or_404(room_id)
        db.session.delete(room)
        db.session.commit()
        flash('Room deleted successfully.', 'warning')
        return redirect(url_for('admin_rooms'))

    @app.route('/admin/users')
    @login_required
    @admin_required
    def admin_users():
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('admin_users.html', users=users)

    @app.route('/admin/bookings')
    @login_required
    @admin_required
    def admin_bookings():
        bookings = Booking.query.order_by(Booking.created_at.desc()).all()
        return render_template('admin_bookings.html', bookings=bookings)

    @app.route('/admin/bookings/status/<int:booking_id>', methods=['POST'])
    @login_required
    @admin_required
    def admin_update_booking_status(booking_id):
        booking_record = Booking.query.get_or_404(booking_id)
        status = request.form.get('status', booking_record.status)
        if status in ['pending', 'confirmed', 'cancelled']:
            booking_record.status = status
            db.session.commit()
            flash('Booking status updated.', 'success')
        else:
            flash('Invalid status selected.', 'danger')
        return redirect(url_for('admin_bookings'))

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500
