# app.py - FIXED VERSION
import os
from datetime import datetime
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg
from psycopg.rows import dict_row
import base64
import io
from dotenv import load_dotenv

# ✅ IMPORTS
import cloudinary
import cloudinary.uploader
import cloudinary.api
import json
import requests
import time
import traceback  # Added for better error tracing

# ✅ Load environment variables
load_dotenv()

# ✅ LOCATION PARSER FUNCTION
def parse_location_data(location_string):
    """
    Parse location string in format: "Address | Latitude | Longitude | MapLink"
    Returns: Dictionary with all components
    """
    if not location_string:
        return {
            'address': '',
            'latitude': None,
            'longitude': None,
            'map_link': None,
            'is_auto_detected': False
        }
    
    # Check if it's in our combined format
    if ' | ' in location_string:
        parts = location_string.split(' | ')
        if len(parts) >= 4:
            try:
                # Format: "Address | LAT | LON | MAP_LINK"
                return {
                    'address': parts[0],
                    'latitude': float(parts[1]) if parts[1] else None,
                    'longitude': float(parts[2]) if parts[2] else None,
                    'map_link': parts[3],
                    'is_auto_detected': True,
                    'full_string': location_string
                }
            except ValueError:
                # If float conversion fails
                pass
    
    # Manual entry (not in combined format)
    return {
        'address': location_string,
        'latitude': None,
        'longitude': None,
        'map_link': None,
        'is_auto_detected': False,
        'full_string': location_string
    }

# ✅ FLASK APP SETUP
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static',
    static_url_path='/static'
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ✅ CLOUDINARY CONFIGURATION
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

# ✅ ADMIN DASHBOARD SYNC SETTINGS
ADMIN_SERVICES_URL = "https://admin-dashboard.onrender.com/admin/export/services/json"
ADMIN_MENU_URL = "https://admin-dashboard.onrender.com/admin/export/menu/json"

# ✅ CACHE SETUP
services_cache = {'data': [], 'timestamp': 0}
menu_cache = {'data': [], 'timestamp': 0}
CACHE_DURATION = 300  # 5 minutes

# ✅ DEFAULT URLS
DEFAULT_AVATAR_URL = "https://res.cloudinary.com/demo/image/upload/v1234567890/profile_pics/default-avatar.png"
SERVICES_FOLDER = "services"
MENU_FOLDER = "menu_items"

# ✅ CONFIGURATION
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

if os.environ.get('RENDER') is None:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ✅ DATABASE FUNCTIONS
def get_db_connection():
    """Establish database connection using DATABASE_URL from environment"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg.connect(database_url, row_factory=dict_row)
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        raise

def init_database():
    """Initialize ALL database tables"""
    try:
        print(f"🔗 Connecting to database...")
        with get_db_connection() as conn:
            print(f"✅ Database connected successfully!")
            
            with conn.cursor() as cur:
                # Check if users table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'users'
                    )
                """)
                users_table_exists = cur.fetchone()['exists']
                
                if not users_table_exists:
                    print("📦 Creating ALL database tables...")
                    
                    # ✅ 1. USERS TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            profile_pic VARCHAR(255),
                            full_name VARCHAR(100) NOT NULL,
                            phone VARCHAR(15) UNIQUE NOT NULL,
                            email VARCHAR(100) UNIQUE NOT NULL,
                            location TEXT NOT NULL,
                            password VARCHAR(255) NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_login TIMESTAMP,
                            is_active BOOLEAN DEFAULT TRUE
                        )
                    """)
                    
                    # ✅ 2. SERVICES TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS services (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(100) NOT NULL,
                            photo VARCHAR(500),
                            price DECIMAL(10, 2) NOT NULL,
                            discount DECIMAL(10, 2) DEFAULT 0,
                            final_price DECIMAL(10, 2) NOT NULL,
                            description TEXT,
                            category VARCHAR(50),
                            status VARCHAR(20) DEFAULT 'active',
                            position INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            cloudinary_id VARCHAR(255)
                        )
                    """)
                    
                    # ✅ 3. MENU TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS menu (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(100) NOT NULL,
                            photo VARCHAR(500),
                            price DECIMAL(10, 2) NOT NULL,
                            discount DECIMAL(10, 2) DEFAULT 0,
                            final_price DECIMAL(10, 2) NOT NULL,
                            description TEXT,
                            category VARCHAR(50),
                            status VARCHAR(20) DEFAULT 'active',
                            position INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            cloudinary_id VARCHAR(255)
                        )
                    """)
                    
                    # ✅ 4. CART TABLE (FIXED: Added created_at column)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS cart (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            item_type VARCHAR(10) CHECK (item_type IN ('service', 'menu')),
                            item_id INTEGER NOT NULL,
                            quantity INTEGER DEFAULT 1,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(user_id, item_type, item_id)
                        )
                    """)
                    
                    # ✅ 5. ORDERS TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS orders (
                            order_id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            user_name VARCHAR(100),
                            user_email VARCHAR(100),
                            user_phone VARCHAR(15),
                            user_address TEXT,
                            items TEXT NOT NULL,
                            total_amount DECIMAL(10, 2) NOT NULL,
                            payment_mode VARCHAR(20) NOT NULL,
                            delivery_location TEXT NOT NULL,
                            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status VARCHAR(20) DEFAULT 'pending',
                            delivery_date TIMESTAMP,
                            notes TEXT
                        )
                    """)
                    
                    # ✅ 6. ORDER ITEMS TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS order_items (
                            order_item_id SERIAL PRIMARY KEY,
                            order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
                            item_type VARCHAR(10) CHECK (item_type IN ('service', 'menu')),
                            item_id INTEGER NOT NULL,
                            item_name VARCHAR(100),
                            item_photo VARCHAR(500),
                            item_description TEXT,
                            quantity INTEGER NOT NULL,
                            price DECIMAL(10, 2) NOT NULL,
                            total DECIMAL(10, 2) NOT NULL
                        )
                    """)
                    
                    # ✅ 7. PAYMENTS TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS payments (
                            payment_id SERIAL PRIMARY KEY,
                            order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            amount DECIMAL(10, 2) NOT NULL,
                            payment_mode VARCHAR(20) NOT NULL,
                            transaction_id VARCHAR(100),
                            payment_status VARCHAR(20) DEFAULT 'pending',
                            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            razorpay_order_id VARCHAR(100),
                            razorpay_payment_id VARCHAR(100),
                            razorpay_signature VARCHAR(200)
                        )
                    """)
                    
                    # ✅ 8. ADDRESSES TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS addresses (
                            address_id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            full_name VARCHAR(100) NOT NULL,
                            phone VARCHAR(15) NOT NULL,
                            address_line1 TEXT NOT NULL,
                            address_line2 TEXT,
                            landmark VARCHAR(100),
                            city VARCHAR(50) NOT NULL,
                            state VARCHAR(50) NOT NULL,
                            pincode VARCHAR(10) NOT NULL,
                            latitude DECIMAL(10, 8),
                            longitude DECIMAL(11, 8),
                            is_default BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # ✅ 9. REVIEWS TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS reviews (
                            review_id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
                            item_type VARCHAR(10) CHECK (item_type IN ('service', 'menu')),
                            item_id INTEGER NOT NULL,
                            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                            comment TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            is_approved BOOLEAN DEFAULT FALSE
                        )
                    """)
                    
                    # ✅ 10. NOTIFICATIONS TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS notifications (
                            notification_id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            title VARCHAR(100) NOT NULL,
                            message TEXT NOT NULL,
                            notification_type VARCHAR(20),
                            is_read BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            read_at TIMESTAMP
                        )
                    """)
                    
                    # ✅ CREATE INDEXES FOR PERFORMANCE
                    print("📊 Creating indexes...")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_services_status ON services(status)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_status ON menu(status)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_addresses_user_id ON addresses(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_order_id ON reviews(order_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)")
                    
                    print("✅ ALL tables created successfully!")
                    
                    # ✅ INSERT SAMPLE DATA
                    print("📝 Adding sample data...")
                    
                    # Sample services
                    sample_services = [
                        ('Home Cleaning', 500.00, 50.00, 450.00, 'Professional home cleaning service', 'Cleaning', 'active', 1),
                        ('Car Wash', 300.00, 30.00, 270.00, 'Complete car washing and detailing', 'Automotive', 'active', 2),
                        ('Plumbing', 800.00, 80.00, 720.00, 'Plumbing repair and maintenance', 'Repair', 'active', 3),
                        ('Electrician', 600.00, 60.00, 540.00, 'Electrical repairs and installations', 'Repair', 'active', 4),
                        ('Gardening', 400.00, 40.00, 360.00, 'Garden maintenance and landscaping', 'Gardening', 'active', 5)
                    ]
                    
                    for service in sample_services:
                        cur.execute("""
                            INSERT INTO services (name, price, discount, final_price, description, category, status, position)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, service)
                    
                    # Sample menu items
                    sample_menu = [
                        ('Pizza', 250.00, 25.00, 225.00, 'Delicious cheese pizza with toppings', 'Italian', 'active', 1),
                        ('Burger', 120.00, 12.00, 108.00, 'Juicy burger with veggies and sauce', 'Fast Food', 'active', 2),
                        ('Pasta', 180.00, 18.00, 162.00, 'Italian pasta with creamy sauce', 'Italian', 'active', 3),
                        ('Salad', 150.00, 15.00, 135.00, 'Fresh vegetable salad with dressing', 'Healthy', 'active', 4),
                        ('Ice Cream', 80.00, 8.00, 72.00, 'Vanilla ice cream with chocolate sauce', 'Dessert', 'active', 5)
                    ]
                    
                    for item in sample_menu:
                        cur.execute("""
                            INSERT INTO menu (name, price, discount, final_price, description, category, status, position)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, item)
                    
                    print(f"✅ Added {len(sample_services)} services and {len(sample_menu)} menu items")
                    
                else:
                    print("✅ Tables already exist, checking for missing columns...")
                    # Check and fix missing columns
                    
                    # Check if cart table has created_at column
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'cart' AND column_name = 'created_at'
                    """)
                    if not cur.fetchone():
                        print("⚠️ Adding missing 'created_at' column to cart table...")
                        cur.execute("ALTER TABLE cart ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    
                    # Check if payments table exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'payments'
                        )
                    """)
                    if not cur.fetchone()['exists']:
                        print("⚠️ Creating missing payments table...")
                        cur.execute("""
                            CREATE TABLE payments (
                                payment_id SERIAL PRIMARY KEY,
                                order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
                                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                                amount DECIMAL(10, 2) NOT NULL,
                                payment_mode VARCHAR(20) NOT NULL,
                                transaction_id VARCHAR(100),
                                payment_status VARCHAR(20) DEFAULT 'pending',
                                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                razorpay_order_id VARCHAR(100),
                                razorpay_payment_id VARCHAR(100),
                                razorpay_signature VARCHAR(200)
                            )
                        """)
                        print("✅ Payments table created")
                
                conn.commit()
                print("✅ Database initialization completed successfully!")
                
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        raise

# ✅ AUTOMATIC DATABASE INITIALIZATION
print("🚀 Starting Bite Me Buddy Application...")
try:
    init_database()
    print("✅ Database initialization completed on startup!")
except Exception as e:
    print(f"⚠️ Database initialization failed: {e}")
    print("⚠️ You may need to run '/init-db' manually")

# ✅ LOGIN REQUIRED DECORATOR
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# ✅ CORE ROUTES
# ============================================

# ✅ HEALTH CHECK
@app.route('/health')
def health_check():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({
            'status': 'healthy',
            'service': 'Bite Me Buddy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ✅ DATABASE INITIALIZATION ROUTE
@app.route('/init-db')
def init_db_route():
    try:
        init_database()
        return jsonify({
            'success': True,
            'message': 'Database initialized successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Database initialization failed: {str(e)}'
        }), 500

# ============================================
# ✅ AUTHENTICATION ROUTES
# ============================================

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        location = request.form.get('location', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        parsed_location = parse_location_data(location)
        
        # Validation
        errors = []
        if not all([full_name, phone, email, parsed_location['address'], password]):
            errors.append('All fields are required')
        if len(phone) < 10:
            errors.append('Invalid phone number')
        if '@' not in email:
            errors.append('Invalid email address')
        if password != confirm_password:
            errors.append('Passwords do not match')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters')
        
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
                    flash(f'Profile photo upload failed: {str(e)}', 'warning')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        hashed_password = generate_password_hash(password)
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM users WHERE phone = %s OR email = %s",
                        (phone, email)
                    )
                    existing_user = cur.fetchone()
                    if existing_user:
                        flash('Phone number or email already registered', 'error')
                        return render_template('register.html')
                    
                    cur.execute(
                        """
                        INSERT INTO users 
                        (profile_pic, full_name, phone, email, location, password)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (profile_pic, full_name, phone, email, location, hashed_password)
                    )
                    user_id = cur.fetchone()['id']
                    conn.commit()
                    
                    # Set session
                    session['user_id'] = user_id
                    session['full_name'] = full_name
                    session['phone'] = phone
                    session['email'] = email
                    session['location'] = parsed_location['address']
                    
                    if parsed_location['is_auto_detected']:
                        session['latitude'] = parsed_location['latitude']
                        session['longitude'] = parsed_location['longitude']
                        session['map_link'] = parsed_location['map_link']
                    
                    session['profile_pic'] = profile_pic
                    session['created_at'] = datetime.now().strftime('%d %b %Y')
                    
                    flash('Registration successful!', 'success')
                    return redirect(url_for('dashboard'))
                    
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        
        if not phone or not password:
            flash('Phone number and password are required', 'error')
            return render_template('login.html')
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM users WHERE phone = %s",
                        (phone,)
                    )
                    user = cur.fetchone()
                    
                    if user and check_password_hash(user['password'], password):
                        # Update last login
                        cur.execute(
                            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
                            (user['id'],)
                        )
                        
                        # Set session
                        session['user_id'] = user['id']
                        session['full_name'] = user['full_name']
                        session['phone'] = user['phone']
                        session['email'] = user['email']
                        
                        parsed_location = parse_location_data(user['location'])
                        session['location'] = parsed_location['address']
                        
                        if parsed_location['is_auto_detected']:
                            session['latitude'] = parsed_location['latitude']
                            session['longitude'] = parsed_location['longitude']
                            session['map_link'] = parsed_location['map_link']
                        
                        session['profile_pic'] = user['profile_pic']
                        
                        # Format created_at
                        if user.get('created_at'):
                            try:
                                if isinstance(user['created_at'], str):
                                    created_at = datetime.strptime(user['created_at'], '%Y-%m-%d %H:%M:%S')
                                else:
                                    created_at = user['created_at']
                                formatted_date = created_at.strftime('%d %b %Y')
                                session['created_at'] = formatted_date
                            except Exception:
                                session['created_at'] = str(user['created_at']).split()[0] if user['created_at'] else 'Recently'
                        else:
                            session['created_at'] = 'Recently'
                        
                        conn.commit()
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
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

# ============================================
# ✅ MAIN PAGES ROUTES
# ============================================

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/services')
@login_required
def services():
    try:
        current_time = time.time()
        
        if (current_time - services_cache['timestamp']) < CACHE_DURATION and services_cache['data']:
            services_list = services_cache['data']
            print("✅ Using cached services data")
        else:
            try:
                response = requests.get(ADMIN_SERVICES_URL, timeout=5)
                if response.status_code == 200:
                    admin_data = response.json()
                    if admin_data.get('success'):
                        services_list = admin_data['services']
                        services_cache['data'] = services_list
                        services_cache['timestamp'] = current_time
                        print("✅ Fetched fresh services from admin")
                    else:
                        raise Exception("Admin API error")
                else:
                    raise Exception(f"Admin API status: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Admin fetch failed: {e}, using local database")
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT * FROM services WHERE status = 'active' ORDER BY position, name"
                        )
                        services_list = cur.fetchall()
        
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
        print(f"Error loading services: {e}")
        return render_template('services.html', services=[])

@app.route('/menu')
@login_required
def menu():
    try:
        current_time = time.time()
        
        if (current_time - menu_cache['timestamp']) < CACHE_DURATION and menu_cache['data']:
            menu_items = menu_cache['data']
            print("✅ Using cached menu data")
        else:
            try:
                response = requests.get(ADMIN_MENU_URL, timeout=5)
                if response.status_code == 200:
                    admin_data = response.json()
                    if admin_data.get('success'):
                        menu_items = admin_data['menu']
                        menu_cache['data'] = menu_items
                        menu_cache['timestamp'] = current_time
                        print("✅ Fetched fresh menu from admin")
                    else:
                        raise Exception("Admin API error")
                else:
                    raise Exception(f"Admin API status: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Admin fetch failed: {e}, using local database")
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT * FROM menu WHERE status = 'active' ORDER BY position, name"
                        )
                        menu_items = cur.fetchall()
        
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
        print(f"Error loading menu: {e}")
        return render_template('menu.html', menu_items=[])

# ============================================
# ✅ CART ROUTES (FIXED)
# ============================================

@app.route('/cart')
@login_required
def cart():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        c.id as cart_id,
                        c.item_type,
                        c.item_id,
                        c.quantity,
                        s.name as service_name,
                        s.photo as service_photo,
                        s.final_price as service_price,
                        s.description as service_description,
                        m.name as menu_name,
                        m.photo as menu_photo,
                        m.final_price as menu_price,
                        m.description as menu_description
                    FROM cart c
                    LEFT JOIN services s ON c.item_type = 'service' AND c.item_id = s.id
                    LEFT JOIN menu m ON c.item_type = 'menu' AND c.item_id = m.id
                    WHERE c.user_id = %s
                    ORDER BY c.created_at DESC
                """, (session['user_id'],))
                
                cart_items = []
                total_amount = 0
                
                for item in cur.fetchall():
                    if item['item_type'] == 'service':
                        item_name = item['service_name']
                        item_price = float(item['service_price'])
                        item_description = item['service_description']
                        db_photo = item['service_photo']
                    else:
                        item_name = item['menu_name']
                        item_price = float(item['menu_price'])
                        item_description = item['menu_description']
                        db_photo = item['menu_photo']
                    
                    photo_url = db_photo
                    if not photo_url or not photo_url.startswith('http'):
                        photo_url = get_cloudinary_photo_for_cart(
                            item_type=item['item_type'],
                            item_id=item['item_id'],
                            item_name=item_name
                        )
                    
                    item_details = {
                        'name': item_name,
                        'photo': photo_url,
                        'price': item_price,
                        'description': item_description
                    }
                    
                    item_total = item_details['price'] * item['quantity']
                    total_amount += item_total
                    
                    cart_items.append({
                        'id': item['cart_id'],
                        'type': item['item_type'],
                        'item_id': item['item_id'],
                        'quantity': item['quantity'],
                        'details': item_details,
                        'item_total': item_total
                    })
                
        return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)
    except Exception as e:
        flash(f'Error loading cart: {str(e)}', 'error')
        return render_template('cart.html', cart_items=[], total_amount=0)

def get_cloudinary_photo_for_cart(item_type, item_id, item_name):
    try:
        folder = SERVICES_FOLDER if item_type == 'service' else MENU_FOLDER
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if item_type == 'service':
                    cur.execute("SELECT photo FROM services WHERE id = %s", (item_id,))
                else:
                    cur.execute("SELECT photo FROM menu WHERE id = %s", (item_id,))
                
                result = cur.fetchone()
                if result and result['photo'] and result['photo'].startswith('http'):
                    return result['photo']
        
        search_name = item_name.lower().replace(' ', '_')
        search_result = cloudinary.Search()\
            .expression(f"folder:{folder} AND filename:{search_name}*")\
            .execute()
        
        if search_result['resources']:
            return search_result['resources'][0]['secure_url']
        
        words = item_name.lower().split()
        for word in words:
            if len(word) > 3:
                search_result = cloudinary.Search()\
                    .expression(f"folder:{folder} AND filename:*{word}*")\
                    .execute()
                
                if search_result['resources']:
                    return search_result['resources'][0]['secure_url']
        
    except Exception as e:
        print(f"Cloudinary search error for cart: {e}")
    
    if item_type == 'service':
        return "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
    else:
        return "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_food.jpg"

@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity', 1))
    
    if not item_type or not item_id:
        return jsonify({'success': False, 'message': 'Missing item information'})
    
    if item_type not in ['service', 'menu']:
        return jsonify({'success': False, 'message': 'Invalid item type'})
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
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
                
        return jsonify({'success': True, 'message': 'Item added to cart'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_cart', methods=['POST'])
@login_required
def update_cart():
    cart_id = request.form.get('cart_id')
    action = request.form.get('action')
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT quantity FROM cart WHERE id = %s AND user_id = %s",
                    (cart_id, session['user_id'])
                )
                item = cur.fetchone()
                
                if not item:
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
                
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/remove_from_cart/<int:cart_id>', methods=['POST'])
@login_required
def remove_from_cart(cart_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM cart WHERE id = %s AND user_id = %s",
                    (cart_id, session['user_id'])
                )
                conn.commit()
        
        flash('Item removed from cart', 'success')
        return redirect(url_for('cart'))
        
    except Exception as e:
        flash(f'Error removing item: {str(e)}', 'error')
        return redirect(url_for('cart'))

# ============================================
# ✅ CHECKOUT & ORDERS ROUTES
# ============================================

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if request.method == 'POST':
        payment_mode = request.form.get('payment_mode')
        delivery_location = request.form.get('delivery_location', '').strip()
        
        print(f"🔍 [CHECKOUT] Starting checkout for user {session['user_id']}")
        print(f"🔍 [CHECKOUT] User: {session.get('full_name')}")
        print(f"🔍 [CHECKOUT] Payment: {payment_mode}")
        print(f"🔍 [CHECKOUT] Delivery: {delivery_location}")
        
        if not payment_mode or not delivery_location:
            flash('Payment mode and delivery location are required', 'error')
            return redirect(url_for('cart'))
        
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                
                # Get cart items with ALL DETAILS
                print(f"🔍 [CHECKOUT] Fetching cart items...")
                cur.execute("""
                    SELECT 
                        c.item_type, 
                        c.item_id, 
                        c.quantity,
                        COALESCE(s.name, m.name) as item_name,
                        COALESCE(s.photo, m.photo) as item_photo,
                        COALESCE(s.description, m.description) as item_description,
                        COALESCE(s.final_price, m.final_price) as price,
                        COALESCE(s.discount, m.discount) as discount
                    FROM cart c
                    LEFT JOIN services s ON c.item_type = 'service' AND c.item_id = s.id
                    LEFT JOIN menu m ON c.item_type = 'menu' AND c.item_id = m.id
                    WHERE c.user_id = %s
                """, (session['user_id'],))
                
                cart_items = cur.fetchall()
                print(f"✅ [CHECKOUT] Got {len(cart_items)} cart items")
                
                if not cart_items:
                    flash('Your cart is empty', 'error')
                    cur.close()
                    return redirect(url_for('cart'))
                
                # Create COMPLETE items list
                total_amount = 0
                items_list = []
                
                for item in cart_items:
                    item_price = float(item['price']) if item['price'] else 0
                    item_quantity = item['quantity']
                    item_total = item_price * item_quantity
                    total_amount += item_total
                    
                    item_data = {
                        'item_type': item['item_type'],
                        'item_id': item['item_id'],
                        'item_name': item['item_name'] or f"{item['item_type'].title()} #{item['item_id']}",
                        'item_photo': item['item_photo'] or '',
                        'item_description': item['item_description'] or '',
                        'quantity': item_quantity,
                        'price': item_price,
                        'total': item_total
                    }
                    
                    if item.get('discount'):
                        item_data['discount'] = float(item['discount'])
                    
                    items_list.append(item_data)
                    print(f"✅ [CHECKOUT] Saving item: {item_data['item_name']}")
                
                # Create JSON with ALL details
                items_json = json.dumps(items_list, indent=2)
                print(f"📋 [CHECKOUT] Items JSON created with {len(items_list)} items")
                
                # Save to orders table WITH USER DETAILS
                print(f"📦 [CHECKOUT] Creating order...")
                cur.execute("""
                    INSERT INTO orders 
                    (user_id, user_name, user_email, user_phone, user_address, 
                     items, total_amount, payment_mode, delivery_location, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    RETURNING order_id
                """, (session['user_id'], session.get('full_name'), session.get('email'), 
                      session.get('phone'), session.get('location'),
                      items_json, total_amount, payment_mode, delivery_location))
                
                order_result = cur.fetchone()
                order_id = order_result['order_id']
                print(f"✅ [CHECKOUT] Order #{order_id} created!")
                
                # Save to order_items table with ALL DETAILS
                inserted_count = 0
                for item in cart_items:
                    try:
                        cur.execute("""
                            INSERT INTO order_items 
                            (order_id, item_type, item_id, item_name, item_photo, 
                             item_description, quantity, price, total)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            order_id, 
                            item['item_type'], 
                            item['item_id'],
                            item['item_name'],
                            item['item_photo'],
                            item['item_description'],
                            item['quantity'],
                            float(item['price']) if item['price'] else 0.0,
                            float(item['price']) * item['quantity'] if item['price'] else 0.0
                        ))
                        inserted_count += 1
                    except Exception as e:
                        print(f"❌ [CHECKOUT] Item insert failed: {e}")
                
                print(f"✅ [CHECKOUT] {inserted_count} items saved to order_items")
                
                # Create payment record
                try:
                    cur.execute("""
                        INSERT INTO payments 
                        (order_id, user_id, amount, payment_mode, payment_status)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (order_id, session['user_id'], total_amount, payment_mode, 'pending'))
                    print(f"✅ [CHECKOUT] Payment record created")
                except Exception as e:
                    print(f"⚠️ [CHECKOUT] Payment record error: {e}")
                
                # Clear cart
                cur.execute("DELETE FROM cart WHERE user_id = %s", (session['user_id'],))
                print(f"✅ [CHECKOUT] Cart cleared")
                
                # Commit everything
                conn.commit()
                cur.close()
                
                print(f"✅ [CHECKOUT] Order #{order_id} completed successfully!")
                print(f"✅ [CHECKOUT] Total: ₹{total_amount}")
                
                flash(f'Order #{order_id} placed successfully!', 'success')
                return redirect(url_for('order_history'))
                
        except Exception as e:
            print(f"❌ [CHECKOUT ERROR] {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Error placing order: {str(e)}', 'error')
            return redirect(url_for('cart'))
    
    # GET REQUEST: Show checkout page with cart data
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get cart items for display
                cur.execute("""
                    SELECT 
                        c.id as cart_id,
                        c.item_type,
                        c.item_id,
                        c.quantity,
                        COALESCE(s.name, m.name) as item_name,
                        COALESCE(s.photo, m.photo) as item_photo,
                        COALESCE(s.description, m.description) as item_description,
                        COALESCE(s.final_price, m.final_price) as price
                    FROM cart c
                    LEFT JOIN services s ON c.item_type = 'service' AND c.item_id = s.id
                    LEFT JOIN menu m ON c.item_type = 'menu' AND c.item_id = m.id
                    WHERE c.user_id = %s
                    ORDER BY c.created_at DESC
                """, (session['user_id'],))
                
                cart_items = []
                cart_total = 0
                
                for item in cur.fetchall():
                    item_details = {
                        'name': item['item_name'],
                        'photo': item['item_photo'],
                        'description': item['item_description'],
                        'price': float(item['price']) if item['price'] else 0
                    }
                    
                    item_total = item_details['price'] * item['quantity']
                    cart_total += item_total
                    
                    cart_items.append({
                        'id': item['cart_id'],
                        'type': item['item_type'],
                        'item_id': item['item_id'],
                        'quantity': item['quantity'],
                        'details': item_details,
                        'item_total': item_total
                    })
                
                print(f"🔍 [CHECKOUT GET] Cart has {len(cart_items)} items, total: ₹{cart_total}")
                
    except Exception as e:
        cart_items = []
        cart_total = 0
        print(f"⚠️ [CHECKOUT GET ERROR] {e}")
    
    return render_template('checkout.html', 
                         cart_items=cart_items, 
                         cart_total=cart_total)

# ============================================
# ✅ ORDER HISTORY ROUTE (FIXED)
# ============================================

@app.route('/order_history')
@login_required
def order_history():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get orders (handle missing payments table)
                cur.execute("""
                    SELECT 
                        o.order_id,
                        o.user_name,
                        o.user_email,
                        o.user_phone,
                        o.user_address,
                        o.items,
                        o.total_amount,
                        o.payment_mode,
                        o.delivery_location,
                        o.status,
                        TO_CHAR(o.order_date, 'DD Mon YYYY, HH12:MI AM') as order_date
                    FROM orders o
                    WHERE o.user_id = %s 
                    ORDER BY o.order_date DESC
                """, (session['user_id'],))
                
                orders_data = cur.fetchall()
                orders_list = []
                
                print(f"✅ [ORDER_HISTORY] Found {len(orders_data)} orders")
                
                for order in orders_data:
                    items_list = []
                    
                    if order['items']:
                        try:
                            json_items = json.loads(order['items'])
                            if isinstance(json_items, list):
                                for item in json_items:
                                    # Create consistent keys for template
                                    items_list.append({
                                        'name': item.get('item_name', item.get('name', 'Unknown Item')),
                                        'item_name': item.get('item_name', item.get('name', 'Unknown Item')),
                                        'type': item.get('item_type', item.get('type', 'unknown')),
                                        'item_type': item.get('item_type', item.get('type', 'unknown')),
                                        'photo': item.get('item_photo', item.get('photo', '')),
                                        'item_photo': item.get('item_photo', item.get('photo', '')),
                                        'description': item.get('item_description', item.get('description', '')),
                                        'item_description': item.get('item_description', item.get('description', '')),
                                        'quantity': int(item.get('quantity', 1)),
                                        'price': float(item.get('price', 0)),
                                        'total': float(item.get('total', 0))
                                    })
                        except Exception as e:
                            print(f"❌ [ORDER_HISTORY] JSON error: {e}")
                            items_list = []
                    
                    # Try to get payment status if payments table exists
                    payment_status = 'pending'
                    try:
                        cur.execute("""
                            SELECT payment_status FROM payments 
                            WHERE order_id = %s LIMIT 1
                        """, (order['order_id'],))
                        payment_result = cur.fetchone()
                        if payment_result:
                            payment_status = payment_result['payment_status']
                    except Exception as payment_error:
                        print(f"⚠️ Payment status error: {payment_error}")
                        payment_status = order.get('payment_mode', 'COD')
                    
                    # Format order with ALL details
                    orders_list.append({
                        'order_id': order['order_id'],
                        'user_name': order['user_name'] or session.get('full_name', ''),
                        'user_email': order['user_email'] or session.get('email', ''),
                        'user_phone': order['user_phone'] or session.get('phone', ''),
                        'user_address': order['user_address'] or session.get('location', ''),
                        'total_amount': float(order['total_amount']) if order['total_amount'] else 0.0,
                        'payment_mode': order['payment_mode'] or 'COD',
                        'payment_status': payment_status,
                        'delivery_location': order['delivery_location'] or 'Location not specified',
                        'status': order['status'] or 'pending',
                        'order_date': order['order_date'] or 'Date not available',
                        'items': items_list  # This should be a list
                    })
        
        # Debug info - FIXED VERSION with proper checks
        if orders_list:
            print(f"🔍 [ORDER_HISTORY] Processing {len(orders_list)} orders")
            if orders_list[0].get('items'):
                items = orders_list[0]['items']
                if isinstance(items, list):
                    print(f"🔍 [ORDER_HISTORY] First order has {len(items)} items")
                    if items:
                        first_item = items[0]
                        has_photo = 'photo' in first_item and first_item['photo']
                        print(f"🔍 [ORDER_HISTORY] First item photo: {'✅' if has_photo else '❌'}")
                else:
                    print(f"⚠️ [ORDER_HISTORY] items is not a list, type: {type(items)}")
            else:
                print(f"⚠️ [ORDER_HISTORY] No items in first order")
        
        return render_template('orders.html', orders=orders_list)
        
    except Exception as e:
        print(f"❌ [ORDER_HISTORY ERROR] {str(e)}")
        traceback.print_exc()
        flash(f'Error loading order history: {str(e)}', 'error')
        return render_template('orders.html', orders=[])

# ============================================
# ✅ ORDER DETAILS ROUTE
# ============================================

@app.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    """View detailed order information"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get order details
                cur.execute("""
                    SELECT 
                        o.*,
                        TO_CHAR(o.order_date, 'DD Mon YYYY, HH12:MI AM') as order_date_formatted,
                        TO_CHAR(o.delivery_date, 'DD Mon YYYY') as delivery_date_formatted
                    FROM orders o
                    WHERE o.order_id = %s AND o.user_id = %s
                """, (order_id, session['user_id']))
                
                order = cur.fetchone()
                
                if not order:
                    flash('Order not found', 'error')
                    return redirect(url_for('order_history'))
                
                # Try to get payment details if payments table exists
                payment_status = 'pending'
                try:
                    cur.execute("""
                        SELECT payment_status, transaction_id, payment_date 
                        FROM payments WHERE order_id = %s
                    """, (order_id,))
                    payment_result = cur.fetchone()
                    if payment_result:
                        order['payment_status'] = payment_result['payment_status']
                        order['transaction_id'] = payment_result['transaction_id']
                        order['payment_date'] = payment_result['payment_date']
                except Exception as e:
                    order['payment_status'] = order.get('payment_mode', 'pending')
                
                # Get order items from order_items table
                cur.execute("""
                    SELECT * FROM order_items 
                    WHERE order_id = %s
                    ORDER BY order_item_id
                """, (order_id,))
                
                order_items = cur.fetchall()
                
                # Parse items JSON if needed
                items_list = []
                if order['items']:
                    try:
                        json_items = json.loads(order['items'])
                        if isinstance(json_items, list):
                            for item in json_items:
                                items_list.append({
                                    'name': item.get('item_name', item.get('name', 'Unknown Item')),
                                    'type': item.get('item_type', item.get('type', 'unknown')),
                                    'photo': item.get('item_photo', item.get('photo', '')),
                                    'description': item.get('item_description', item.get('description', '')),
                                    'quantity': int(item.get('quantity', 1)),
                                    'price': float(item.get('price', 0)),
                                    'total': float(item.get('total', 0))
                                })
                    except Exception as e:
                        print(f"JSON parse error: {e}")
                
                # If items_list is empty, use order_items table
                if not items_list and order_items:
                    for item in order_items:
                        items_list.append({
                            'name': item.get('item_name', f"{item['item_type'].title()} #{item['item_id']}"),
                            'type': item['item_type'],
                            'photo': item.get('item_photo', ''),
                            'description': item.get('item_description', ''),
                            'quantity': item['quantity'],
                            'price': float(item['price']),
                            'total': float(item['total'])
                        })
                
                return render_template('order_details.html', 
                                     order=order, 
                                     items=items_list,
                                     order_items=order_items)
                
    except Exception as e:
        print(f"Order details error: {e}")
        traceback.print_exc()
        flash(f'Error loading order details: {str(e)}', 'error')
        return redirect(url_for('order_history'))

# ============================================
# ✅ PROFILE ROUTES
# ============================================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        location = request.form.get('location', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        parsed_location = parse_location_data(location)
        
        errors = []
        if not all([full_name, email, parsed_location['address']]):
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
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('profile.html')
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
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
                    
                    update_fields = ["full_name = %(full_name)s", 
                                    "email = %(email)s", 
                                    "location = %(location)s",
                                    "profile_pic = %(profile_pic)s"]
                    
                    if new_password:
                        hashed_password = generate_password_hash(new_password)
                        update_data['password'] = hashed_password
                        update_fields.append("password = %(password)s")
                    
                    update_query = f"""
                        UPDATE users 
                        SET {', '.join(update_fields)}
                        WHERE id = %(user_id)s
                    """
                    
                    cur.execute(update_query, update_data)
                    conn.commit()
                    
                    # Update session
                    session['full_name'] = full_name
                    session['email'] = email
                    session['location'] = parsed_location['address']
                    
                    if parsed_location['is_auto_detected']:
                        session['latitude'] = parsed_location['latitude']
                        session['longitude'] = parsed_location['longitude']
                        session['map_link'] = parsed_location['map_link']
                    
                    session['profile_pic'] = profile_pic
                    
                    flash('Profile updated successfully!', 'success')
                    return redirect(url_for('profile'))
                    
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
            return render_template('profile.html')
    
    return render_template('profile.html')

# ============================================
# ✅ ADDRESS ROUTES
# ============================================

@app.route('/addresses')
@login_required
def addresses():
    """View and manage addresses"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM addresses 
                    WHERE user_id = %s 
                    ORDER BY is_default DESC, created_at DESC
                """, (session['user_id'],))
                
                addresses_list = cur.fetchall()
                
        return render_template('addresses.html', addresses=addresses_list)
    except Exception as e:
        flash(f'Error loading addresses: {str(e)}', 'error')
        return render_template('addresses.html', addresses=[])

@app.route('/add_address', methods=['POST'])
@login_required
def add_address():
    """Add new address"""
    try:
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        address_line1 = request.form.get('address_line1', '').strip()
        address_line2 = request.form.get('address_line2', '').strip()
        landmark = request.form.get('landmark', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        is_default = request.form.get('is_default') == 'on'
        
        if not all([full_name, phone, address_line1, city, state, pincode]):
            flash('Please fill all required fields', 'error')
            return redirect(url_for('addresses'))
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # If setting as default, remove default from others
                if is_default:
                    cur.execute("""
                        UPDATE addresses 
                        SET is_default = FALSE 
                        WHERE user_id = %s
                    """, (session['user_id'],))
                
                cur.execute("""
                    INSERT INTO addresses 
                    (user_id, full_name, phone, address_line1, address_line2, 
                     landmark, city, state, pincode, is_default)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (session['user_id'], full_name, phone, address_line1, 
                      address_line2, landmark, city, state, pincode, is_default))
                
                conn.commit()
        
        flash('Address added successfully!', 'success')
        return redirect(url_for('addresses'))
        
    except Exception as e:
        flash(f'Error adding address: {str(e)}', 'error')
        return redirect(url_for('addresses'))

# ============================================
# ✅ NOTIFICATIONS ROUTES
# ============================================

@app.route('/notifications')
@login_required
def notifications():
    """View notifications"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get notifications
                cur.execute("""
                    SELECT * FROM notifications 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                """, (session['user_id'],))
                
                notifications_list = cur.fetchall()
                
                # Mark as read
                cur.execute("""
                    UPDATE notifications 
                    SET is_read = TRUE, read_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND is_read = FALSE
                """, (session['user_id'],))
                
                conn.commit()
        
        return render_template('notifications.html', notifications=notifications_list)
    except Exception as e:
        flash(f'Error loading notifications: {str(e)}', 'error')
        return render_template('notifications.html', notifications=[])

# ============================================
# ✅ DEBUG & UTILITY ROUTES
# ============================================

@app.route('/debug-orders')
@login_required
def debug_orders():
    """Debug orders data"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count, 
                           MAX(order_date) as latest_order,
                           MIN(order_date) as first_order
                    FROM orders 
                    WHERE user_id = %s
                """, (session['user_id'],))
                orders_stats = cur.fetchone()
                
                cur.execute("""
                    SELECT COUNT(*) as count 
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.order_id
                    WHERE o.user_id = %s
                """, (session['user_id'],))
                order_items_stats = cur.fetchone()
                
                cur.execute("""
                    SELECT 
                        o.order_id, 
                        o.total_amount,
                        o.status,
                        TO_CHAR(o.order_date, 'DD Mon YYYY HH24:MI') as order_date,
                        LENGTH(o.items) as items_length,
                        LEFT(o.items, 100) as items_preview,
                        COUNT(oi.order_item_id) as item_count
                    FROM orders o
                    LEFT JOIN order_items oi ON o.order_id = oi.order_id
                    WHERE o.user_id = %s
                    GROUP BY o.order_id, o.items, o.order_date
                    ORDER BY o.order_date DESC
                    LIMIT 5
                """, (session['user_id'],))
                
                sample_orders = cur.fetchall()
        
        return jsonify({
            'success': True,
            'user_id': session['user_id'],
            'user_name': session.get('full_name', 'Unknown'),
            'orders_stats': {
                'total_orders': orders_stats['count'],
                'latest_order': str(orders_stats['latest_order']) if orders_stats['latest_order'] else 'None',
                'first_order': str(orders_stats['first_order']) if orders_stats['first_order'] else 'None'
            },
            'order_items_stats': {
                'total_items': order_items_stats['count']
            },
            'sample_orders': sample_orders
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/fix-all-orders')
@login_required
def fix_all_orders():
    """Fix all orders to include complete details"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT order_id, items 
                FROM orders 
                WHERE user_id = %s 
                ORDER BY order_date
            """, (session['user_id'],))
            
            orders = cur.fetchall()
            
            if not orders:
                return "<h2>No orders found for this user</h2>"
            
            results = []
            total_fixed = 0
            
            for order in orders:
                order_id = order['order_id']
                items_json = order['items']
                
                if items_json:
                    try:
                        items_list = json.loads(items_json)
                        new_items = []
                        
                        for item in items_list:
                            # Get missing details
                            if item.get('item_type') == 'service':
                                cur.execute("""
                                    SELECT name, photo, description 
                                    FROM services 
                                    WHERE id = %s
                                """, (item.get('item_id'),))
                            else:
                                cur.execute("""
                                    SELECT name, photo, description 
                                    FROM menu 
                                    WHERE id = %s
                                """, (item.get('item_id'),))
                            
                            details = cur.fetchone()
                            
                            # Update item
                            if details:
                                item['item_name'] = details['name']
                                item['item_photo'] = details['photo']
                                item['item_description'] = details['description']
                            
                            new_items.append(item)
                        
                        # Update database
                        new_json = json.dumps(new_items)
                        cur.execute("""
                            UPDATE orders 
                            SET items = %s 
                            WHERE order_id = %s
                        """, (new_json, order_id))
                        
                        total_fixed += 1
                        results.append(f"✅ Order #{order_id}: Fixed")
                        
                    except Exception as e:
                        results.append(f"❌ Order #{order_id}: ERROR - {str(e)}")
                else:
                    results.append(f"⚠️ Order #{order_id}: No items JSON")
            
            conn.commit()
            cur.close()
            
            return f"""
            <h2>Order Fix Results</h2>
            <p>User: {session.get('full_name')} (ID: {session['user_id']})</p>
            <p>Total Orders: {len(orders)}</p>
            <p>Fixed: {total_fixed}</p>
            <hr>
            {'<br>'.join(results)}
            <hr>
            <p><a href="/order_history">← Back to Order History</a></p>
            """
            
    except Exception as e:
        return f"<h2>Error</h2><p>{str(e)}</p>"

# ============================================
# ✅ CLOUDINARY PROFILE PICTURE UPLOAD
# ============================================

@app.route('/upload-profile-pic', methods=['POST'])
@login_required
def upload_profile_pic():
    try:
        if 'profile_pic' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'})
        
        file = request.files['profile_pic']
        
        if not file or file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Invalid file type'})
        
        public_id = f"profile_pic_{session['user_id']}_{secrets.token_hex(8)}"
        
        try:
            upload_result = cloudinary.uploader.upload(
                file,
                folder="profile_pics",
                public_id=public_id,
                overwrite=True,
                transformation=[
                    {'width': 500, 'height': 500, 'crop': 'fill'},
                    {'quality': 'auto', 'fetch_format': 'auto'}
                ]
            )
            
            uploaded_url = upload_result.get('secure_url')
            
            if not uploaded_url:
                return jsonify({'success': False, 'message': 'Upload failed'})
            
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET profile_pic = %s WHERE id = %s",
                        (uploaded_url, session['user_id'])
                    )
                    conn.commit()
            
            session['profile_pic'] = uploaded_url
            
            return jsonify({
                'success': True,
                'url': uploaded_url,
                'message': 'Profile picture updated'
            })
            
        except Exception as upload_error:
            print(f"Cloudinary upload error: {upload_error}")
            return jsonify({'success': False, 'message': f'Upload failed: {str(upload_error)}'})
            
    except Exception as e:
        print(f"General error: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# ============================================
# ✅ SERVICE & MENU DETAILS ROUTES
# ============================================

@app.route('/get_service_details/<int:service_id>')
@login_required
def get_service_details(service_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM services WHERE id = %s AND status = 'active'",
                    (service_id,)
                )
                service = cur.fetchone()
                
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
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM menu WHERE id = %s AND status = 'active'",
                    (menu_id,)
                )
                menu_item = cur.fetchone()
                
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

# ============================================
# ✅ FORGOT PASSWORD ROUTES
# ============================================

@app.route('/forgot-password')
def forgot_password():
    firebase_config = {
        'FIREBASE_API_KEY': 'AIzaSyBmZG2Xi5WNXsEbY1gj4MQ6PKnS0gu1S4s',
        'FIREBASE_AUTH_DOMAIN': 'bite-me-buddy.firebaseapp.com',
        'FIREBASE_PROJECT_ID': 'bite-me-buddy',
        'FIREBASE_APP_ID': '1:387282094580:web:422e09cff55a0ed47bd1a1',
        'FIREBASE_TEST_PHONE': '+911234567890',
        'FIREBASE_TEST_OTP': '123456'
    }
    return render_template('forgot_password.html', **firebase_config)

@app.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '').strip()
        
        if not mobile or not password:
            flash('Please fill all fields', 'error')
            return redirect('/forgot-password')
        
        if not mobile.startswith('+'):
            if mobile.isdigit() and len(mobile) == 10:
                mobile = '+91' + mobile
            else:
                flash('Please enter a valid mobile number with country code', 'error')
                return redirect('/forgot-password')
        
        hashed_password = generate_password_hash(password)
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE phone = %s", (mobile,))
                    user = cur.fetchone()
                    
                    if not user:
                        flash('Mobile number not registered', 'error')
                        return redirect('/forgot-password')
                    
                    cur.execute(
                        "UPDATE users SET password = %s WHERE phone = %s",
                        (hashed_password, mobile)
                    )
                    
                    if cur.rowcount == 0:
                        flash('Failed to update password', 'error')
                        return redirect('/forgot-password')
                    
                    conn.commit()
                    
                    flash('Password reset successful! Please login with new password.', 'success')
                    return redirect(url_for('login'))
                    
        except Exception as db_error:
            flash(f'Database error: {str(db_error)}', 'error')
            return redirect('/forgot-password')
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect('/forgot-password')

# ============================================
# ✅ CONTEXT PROCESSOR
# ============================================

@app.context_processor
def utility_processor():
    def get_user_friendly_location(location_string):
        parsed = parse_location_data(location_string)
        return parsed['address']
    
    return dict(
        get_user_location=get_user_friendly_location
    )

# ============================================
# ✅ APPLICATION STARTUP
# ============================================

if __name__ == '__main__':
    is_render = os.environ.get('RENDER') is not None
    
    if not is_render:
        print("🚀 Starting in LOCAL DEVELOPMENT mode")
        try:
            print("✅ Database already initialized at startup!")
        except Exception as e:
            print(f"⚠️ Error: {e}")
        
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("🚀 Starting in RENDER PRODUCTION mode")
        print("✅ Application ready for gunicorn")
