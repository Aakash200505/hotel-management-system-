# Hotel Booking System (Flask)

## Run

```bash
pip install flask flask_sqlalchemy flask_login
python app.py
```

## Default Admin

- Email: `admin@hotel.com`
- Password: `admin123`

## Features

- User auth (register/login/logout) with hashed passwords
- Role-based access (user/admin)
- Hotel CRUD with image upload
- Room inventory and dynamic pricing controls
- Search/filter by location, price, rating, and date availability
- Booking flow with check-in/check-out validation and price calc
- Dummy payment flow with success/failure states and receipt
- User dashboard (booking history, cancel booking, profile update)
- Admin dashboard (bookings, revenue, users, analytics chart)
- Flash messages, sessions, form validation, 404/500 pages
