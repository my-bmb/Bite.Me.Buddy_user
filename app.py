# app.py - COMPLETE UPDATED VERSION FOR RENDER (Python 3.13 Compatible)
import os
from datetime import datetime
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg
from psycopg.rows import dict_row
import cloudinary
import cloudinary.uploader
import cloudinary.api

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

# Default avatar URL
DEFAULT_AVATAR_URL = "https://res.cloudinary.com/demo/image/upload/v1234567890/profile_pics/default-avatar.png"

# Cloudinary Folders
SERVICES_FOLDER = "services"
MENU_FOLDER = "menu_items"

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """Establish database connection"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        # Local development fallback
        database_url = "postgresql://database_md9y_user:seYTKwtdui8FLCquSsmojB1CFjIlbUmk@dpg-d5ehqm5actks73c8a8og-a/database_md9y"
    
    # Fix for Render PostgreSQL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg.connect(database_url, row_factory=dict_row)
        return conn
    except psycopg.OperationalError as e:
        # If connection fails, try with SSL mode
        if "SSL" in str(e) or "ssl" in str(e):
            if "sslmode" not in database_url:
                database_url += "?sslmode=require"
                try:
                    conn = psycopg.connect(database_url, row_factory=dict_row)
                    print("✅ Connected with SSL mode")
                    return conn
                except Exception as e2:
                    print(f"SSL connection failed: {e2}")
        print(f"Database connection error: {e}")
        raise

def create_tables_if_not_exists():
    """Create tables if they don't exist - AUTO CREATION FOR DEPLOYMENT"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # USERS TABLE
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                profile_pic VARCHAR(255),
                full_name VARCHAR(100) NOT NULL,
                phone VARCHAR(15) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                location TEXT NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # SERVICES TABLE
        cur.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                photo VARCHAR(255),
                price DECIMAL(10, 2) NOT NULL,
                discount DECIMAL(10, 2) DEFAULT 0,
                final_price DECIMAL(10, 2) NOT NULL,
                description TEXT,
                status VARCHAR(20) DEFAULT 'active'
            )
        """)
        
        # MENU TABLE
        cur.execute("""
            CREATE TABLE IF NOT EXISTS menu (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                photo VARCHAR(255),
                price DECIMAL(10, 2) NOT NULL,
                discount DECIMAL(10, 2) DEFAULT 0,
                final_price DECIMAL(10, 2) NOT NULL,
                description TEXT,
                status VARCHAR(20) DEFAULT 'active'
            )
        """)
        
        # CART TABLE
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                item_type VARCHAR(10) CHECK (item_type IN ('service', 'menu')),
                item_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                UNIQUE(user_id, item_type, item_id)
            )
        """)
        
        # ORDERS TABLE
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                total_amount DECIMAL(10, 2) NOT NULL,
                payment_mode VARCHAR(20) NOT NULL,
                delivery_location TEXT NOT NULL,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'pending'
            )
        """)
        
        # ORDER_ITEMS TABLE
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                order_item_id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
                item_type VARCHAR(10) CHECK (item_type IN ('service', 'menu')),
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                price DECIMAL(10, 2) NOT NULL
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database tables created/verified successfully")
        return True
        
    except Exception as e:
        print(f"⚠️ Table creation error: {e}")
        return False

# 🚀 CRITICAL FIX FOR RENDER FREE PLAN: Initialize database on app start
print("🔄 Initializing database for Render Free Plan...")
if create_tables_if_not_exists():
    print("✅ Database initialization completed successfully!")
else:
    print("⚠️ Database initialization encountered issues, will retry on first request")

def login_required(f):
    """Decorator to protect routes requiring login"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    """Home page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        location = request.form.get('location', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validate inputs
        errors = []
        if not all([full_name, phone, email, location, password]):
            errors.append('All fields are required')
        if len(phone) < 10:
            errors.append('Invalid phone number')
        if '@' not in email:
            errors.append('Invalid email address')
        if password != confirm_password:
            errors.append('Passwords do not match')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters')
        
        # Profile picture handling
        profile_pic = DEFAULT_AVATAR_URL
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                try:
                    result = cloudinary.uploader.upload(
                        file,
                        folder="profile_pics",
                        public_id=f"user_{secrets.token_hex(8)}",
                        overwrite=True,
                        transformation=[
                            {'width': 500, 'height': 500, 'crop': 'fill'},
                            {'quality': 'auto', 'fetch_format': 'auto'}
                        ]
                    )
                    profile_pic = result["secure_url"]
                except Exception as e:
                    print(f"Cloudinary upload failed: {e}")
                    profile_pic = DEFAULT_AVATAR_URL
            elif file and file.filename:
                errors.append('Invalid file type. Allowed: png, jpg, jpeg, gif')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check if user exists
            cur.execute(
                "SELECT id FROM users WHERE phone = %s OR email = %s",
                (phone, email)
            )
            existing_user = cur.fetchone()
            if existing_user:
                flash('Phone number or email already registered', 'error')
                return render_template('register.html')
            
            # Insert new user
            cur.execute(
                """
                INSERT INTO users 
                (profile_pic, full_name, phone, email, location, password)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (profile_pic, full_name, phone, email, location, hashed_password)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            
            # Set session
            session['user_id'] = user_id
            session['full_name'] = full_name
            session['phone'] = phone
            session['email'] = email
            session['location'] = location
            session['profile_pic'] = profile_pic
            session['created_at'] = datetime.now().strftime('%d %b %Y')
            
            cur.close()
            conn.close()
            
            flash('Registration successful!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        
        if not phone or not password:
            flash('Phone number and password are required', 'error')
            return render_template('login.html')
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute(
                "SELECT * FROM users WHERE phone = %s",
                (phone,)
            )
            user = cur.fetchone()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['full_name'] = user['full_name']
                session['phone'] = user['phone']
                session['email'] = user['email']
                session['location'] = user['location']
                session['profile_pic'] = user['profile_pic']
                
                if user.get('created_at'):
                    created_at = user['created_at']
                    try:
                        if isinstance(created_at, str):
                            created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                        session['created_at'] = created_at.strftime('%d %b %Y')
                    except:
                        session['created_at'] = str(created_at).split()[0] if created_at else 'Recently'
                else:
                    session['created_at'] = 'Recently'
                
                cur.close()
                conn.close()
                
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid phone number or password', 'error')
                return render_template('login.html')
                
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html')

@app.route('/services')
@login_required
def services():
    """Display services"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT * FROM services WHERE status = 'active' ORDER BY name"
        )
        services_list = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Cloudinary integration
        try:
            cloudinary_services = cloudinary.api.resources(
                type="upload",
                prefix=SERVICES_FOLDER,
                max_results=100
            )
            
            cloudinary_images = {}
            for resource in cloudinary_services.get('resources', []):
                filename = os.path.splitext(os.path.basename(resource['public_id']))[0]
                service_name = filename.replace('_', ' ').title()
                cloudinary_images[service_name.lower()] = resource['secure_url']
            
            for service in services_list:
                service_name = service['name'].lower()
                if service_name in cloudinary_images:
                    service['photo'] = cloudinary_images[service_name]
                elif not service.get('photo'):
                    service['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
                    
        except Exception as cloudinary_error:
            print(f"Cloudinary error: {cloudinary_error}")
            
        return render_template('services.html', services=services_list)
    except Exception as e:
        flash(f'Error loading services: {str(e)}', 'error')
        return render_template('services.html', services=[])

@app.route('/menu')
@login_required
def menu():
    """Display menu items"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT * FROM menu WHERE status = 'active' ORDER BY name"
        )
        menu_items = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Cloudinary integration
        try:
            cloudinary_menu = cloudinary.api.resources(
                type="upload",
                prefix=MENU_FOLDER,
                max_results=100
            )
            
            cloudinary_images = {}
            for resource in cloudinary_menu.get('resources', []):
                filename = os.path.splitext(os.path.basename(resource['public_id']))[0]
                menu_name = filename.replace('_', ' ').title()
                cloudinary_images[menu_name.lower()] = resource['secure_url']
            
            for menu_item in menu_items:
                item_name = menu_item['name'].lower()
                if item_name in cloudinary_images:
                    menu_item['photo'] = cloudinary_images[item_name]
                elif not menu_item.get('photo'):
                    menu_item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_food.jpg"
                    
        except Exception as cloudinary_error:
            print(f"Cloudinary error: {cloudinary_error}")
            
        return render_template('menu.html', menu_items=menu_items)
    except Exception as e:
        flash(f'Error loading menu: {str(e)}', 'error')
        return render_template('menu.html', menu_items=[])

@app.route('/cart')
@login_required
def cart():
    """Display cart"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT c.id, c.item_type, c.item_id, c.quantity,
                   s.name as service_name, s.photo as service_photo,
                   s.final_price as service_price, s.description as service_desc,
                   m.name as menu_name, m.photo as menu_photo,
                   m.final_price as menu_price, m.description as menu_desc
            FROM cart c
            LEFT JOIN services s ON c.item_type = 'service' AND c.item_id = s.id
            LEFT JOIN menu m ON c.item_type = 'menu' AND c.item_id = m.id
            WHERE c.user_id = %s
            ORDER BY c.id DESC
        """, (session['user_id'],))
        
        cart_items = []
        total_amount = 0
        
        for item in cur.fetchall():
            if item['item_type'] == 'service':
                item_details = {
                    'name': item['service_name'],
                    'photo': item['service_photo'],
                    'price': float(item['service_price']),
                    'description': item['service_desc']
                }
            else:
                item_details = {
                    'name': item['menu_name'],
                    'photo': item['menu_photo'],
                    'price': float(item['menu_price']),
                    'description': item['menu_desc']
                }
            
            item_total = item_details['price'] * item['quantity']
            total_amount += item_total
            
            cart_items.append({
                'id': item['id'],
                'type': item['item_type'],
                'item_id': item['item_id'],
                'quantity': item['quantity'],
                'details': item_details,
                'item_total': item_total
            })
        
        cur.close()
        conn.close()
        
        return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)
    except Exception as e:
        flash(f'Error loading cart: {str(e)}', 'error')
        return render_template('cart.html', cart_items=[], total_amount=0)

@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    """Add to cart"""
    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity', 1))
    
    if not item_type or not item_id:
        return jsonify({'success': False, 'message': 'Missing item information'})
    
    if item_type not in ['service', 'menu']:
        return jsonify({'success': False, 'message': 'Invalid item type'})
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if item_type == 'service':
            cur.execute(
                "SELECT id FROM services WHERE id = %s AND status = 'active'",
                (item_id,)
            )
        else:
            cur.execute(
                "SELECT id FROM menu WHERE id = %s AND status = 'active'",
                (item_id,)
            )
        
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Item not available'})
        
        cur.execute("""
            SELECT id, quantity FROM cart 
            WHERE user_id = %s AND item_type = %s AND item_id = %s
        """, (session['user_id'], item_type, item_id))
        
        existing = cur.fetchone()
        
        if existing:
            new_quantity = existing['quantity'] + quantity
            cur.execute("""
                UPDATE cart SET quantity = %s 
                WHERE id = %s
            """, (new_quantity, existing['id']))
        else:
            cur.execute("""
                INSERT INTO cart (user_id, item_type, item_id, quantity)
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], item_type, item_id, quantity))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Item added to cart'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_cart', methods=['POST'])
@login_required
def update_cart():
    """Update cart quantity"""
    cart_id = request.form.get('cart_id')
    action = request.form.get('action')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT quantity FROM cart WHERE id = %s AND user_id = %s",
            (cart_id, session['user_id'])
        )
        item = cur.fetchone()
        
        if not item:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Item not found'})
        
        new_quantity = item['quantity']
        
        if action == 'increase':
            new_quantity += 1
        elif action == 'decrease':
            new_quantity -= 1
        
        if new_quantity <= 0:
            cur.execute("DELETE FROM cart WHERE id = %s", (cart_id,))
        else:
            cur.execute(
                "UPDATE cart SET quantity = %s WHERE id = %s",
                (new_quantity, cart_id)
            )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/remove_from_cart/<int:cart_id>', methods=['POST'])
@login_required
def remove_from_cart(cart_id):
    """Remove from cart"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "DELETE FROM cart WHERE id = %s AND user_id = %s",
            (cart_id, session['user_id'])
        )
        conn.commit()
        
        cur.close()
        conn.close()
        
        flash('Item removed from cart', 'success')
        return redirect(url_for('cart'))
        
    except Exception as e:
        flash(f'Error removing item: {str(e)}', 'error')
        return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Checkout"""
    if request.method == 'POST':
        payment_mode = request.form.get('payment_mode')
        delivery_location = request.form.get('delivery_location', '').strip()
        
        if not payment_mode or not delivery_location:
            flash('Payment mode and delivery location are required', 'error')
            return redirect(url_for('cart'))
        
        if payment_mode not in ['COD', 'UPI', 'Card']:
            flash('Invalid payment mode', 'error')
            return redirect(url_for('cart'))
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT c.item_type, c.item_id, c.quantity,
                       COALESCE(s.final_price, m.final_price) as price
                FROM cart c
                LEFT JOIN services s ON c.item_type = 'service' AND c.item_id = s.id
                LEFT JOIN menu m ON c.item_type = 'menu' AND c.item_id = m.id
                WHERE c.user_id = %s
            """, (session['user_id'],))
            
            cart_items = cur.fetchall()
            
            if not cart_items:
                flash('Your cart is empty', 'error')
                return redirect(url_for('cart'))
            
            total_amount = sum(float(item['price']) * item['quantity'] for item in cart_items)
            
            cur.execute("""
                INSERT INTO orders 
                (user_id, total_amount, payment_mode, delivery_location, status)
                VALUES (%s, %s, %s, %s, 'pending')
                RETURNING order_id
            """, (session['user_id'], total_amount, payment_mode, delivery_location))
            
            order = cur.fetchone()
            order_id = order[0]
            
            for item in cart_items:
                cur.execute("""
                    INSERT INTO order_items 
                    (order_id, item_type, item_id, quantity, price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (order_id, item['item_type'], item['item_id'], 
                      item['quantity'], item['price']))
            
            cur.execute("DELETE FROM cart WHERE user_id = %s", (session['user_id'],))
            
            conn.commit()
            cur.close()
            conn.close()
            
            flash('Order placed successfully!', 'success')
            return redirect(url_for('order_history'))
            
        except Exception as e:
            flash(f'Error placing order: {str(e)}', 'error')
            return redirect(url_for('cart'))
    
    return render_template('checkout.html')

@app.route('/order_history')
@login_required
def order_history():
    """Order history"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT * FROM orders 
            WHERE user_id = %s 
            ORDER BY order_date DESC
        """, (session['user_id'],))
        orders = cur.fetchall()
        
        orders_with_items = []
        for order in orders:
            cur.execute("""
                SELECT oi.*, 
                       COALESCE(s.name, m.name) as item_name,
                       COALESCE(s.photo, m.photo) as item_photo
                FROM order_items oi
                LEFT JOIN services s ON oi.item_type = 'service' AND oi.item_id = s.id
                LEFT JOIN menu m ON oi.item_type = 'menu' AND oi.item_id = m.id
                WHERE oi.order_id = %s
            """, (order['order_id'],))
            
            items = cur.fetchall()
            order['items'] = items
            orders_with_items.append(order)
        
        cur.close()
        conn.close()
        
        return render_template('orders.html', orders=orders_with_items)
    except Exception as e:
        flash(f'Error loading order history: {str(e)}', 'error')
        return render_template('orders.html', orders=[])

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile"""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        location = request.form.get('location', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        errors = []
        if not all([full_name, email, location]):
            errors.append('All fields except password are required')
        if '@' not in email:
            errors.append('Invalid email address')
        if new_password and len(new_password) < 6:
            errors.append('Password must be at least 6 characters')
        if new_password and new_password != confirm_password:
            errors.append('Passwords do not match')
        
        profile_pic = session.get('profile_pic', DEFAULT_AVATAR_URL)
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                try:
                    result = cloudinary.uploader.upload(
                        file,
                        folder="profile_pics",
                        public_id=f"user_{secrets.token_hex(8)}",
                        overwrite=True,
                        transformation=[
                            {'width': 500, 'height': 500, 'crop': 'fill'},
                            {'quality': 'auto', 'fetch_format': 'auto'}
                        ]
                    )
                    profile_pic = result["secure_url"]
                except Exception as e:
                    flash(f'Profile photo upload failed: {str(e)}', 'warning')
                    profile_pic = session.get('profile_pic', DEFAULT_AVATAR_URL)
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('profile.html')
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute(
                "SELECT id FROM users WHERE email = %s AND id != %s",
                (email, session['user_id'])
            )
            if cur.fetchone():
                flash('Email already registered to another account', 'error')
                return render_template('profile.html')
            
            update_data = {
                'full_name': full_name,
                'email': email,
                'location': location,
                'profile_pic': profile_pic,
                'user_id': session['user_id']
            }
            
            update_fields = ["full_name = %s", "email = %s", "location = %s", "profile_pic = %s"]
            values = [full_name, email, location, profile_pic]
            
            if new_password:
                hashed_password = generate_password_hash(new_password)
                update_fields.append("password = %s")
                values.append(hashed_password)
            
            values.append(session['user_id'])
            
            update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
            
            cur.execute(update_query, values)
            conn.commit()
            
            session['full_name'] = full_name
            session['email'] = email
            session['location'] = location
            session['profile_pic'] = profile_pic
            
            cur.close()
            conn.close()
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
            
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
            return render_template('profile.html')
    
    return render_template('profile.html')

@app.route('/get_service_details/<int:service_id>')
@login_required
def get_service_details(service_id):
    """Service details"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT * FROM services WHERE id = %s AND status = 'active'",
            (service_id,)
        )
        service = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if service:
            service_name = service['name'].lower()
            try:
                search_result = cloudinary.api.resources_by_asset_folder(
                    asset_folder=SERVICES_FOLDER,
                    max_results=100
                )
                
                for resource in search_result.get('resources', []):
                    filename = os.path.splitext(os.path.basename(resource['public_id']))[0]
                    if service_name in filename.lower():
                        service['photo'] = resource['secure_url']
                        break
            except Exception as cloudinary_error:
                print(f"Cloudinary error: {cloudinary_error}")
            
            return jsonify({
                'success': True,
                'service': {
                    'name': service['name'],
                    'photo': service.get('photo', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg'),
                    'price': float(service['price']),
                    'discount': float(service['discount']),
                    'final_price': float(service['final_price']),
                    'description': service['description']
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Service not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_menu_details/<int:menu_id>')
@login_required
def get_menu_details(menu_id):
    """Menu details"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT * FROM menu WHERE id = %s AND status = 'active'",
            (menu_id,)
        )
        menu_item = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if menu_item:
            item_name = menu_item['name'].lower()
            try:
                search_result = cloudinary.api.resources_by_asset_folder(
                    asset_folder=MENU_FOLDER,
                    max_results=100
                )
                
                for resource in search_result.get('resources', []):
                    filename = os.path.splitext(os.path.basename(resource['public_id']))[0]
                    if item_name in filename.lower():
                        menu_item['photo'] = resource['secure_url']
                        break
            except Exception as cloudinary_error:
                print(f"Cloudinary error: {cloudinary_error}")
            
            return jsonify({
                'success': True,
                'menu': {
                    'name': menu_item['name'],
                    'photo': menu_item.get('photo', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_food.jpg'),
                    'price': float(menu_item['price']),
                    'discount': float(menu_item['discount']),
                    'final_price': float(menu_item['final_price']),
                    'description': menu_item['description']
                }
            })
        else:
            return jsonify({'success': False, 'message': 'Menu item not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    # Create uploads directory
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Check environment
    required_env_vars = ['DATABASE_URL']
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"⚠️ WARNING: Missing environment variables: {missing_vars}")
    
    # Get port
    port = int(os.environ.get('PORT', 5000))
    
    app.run(debug=False, host='0.0.0.0', port=port)
