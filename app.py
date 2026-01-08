# app.py - COMPLETELY FIXED WITH RENDER LOGS AND AUTO DB INIT
import os
import sys
from datetime import datetime
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import psycopg
from psycopg.rows import dict_row
import base64
import io
import time
import traceback
from dotenv import load_dotenv  # ✅ ADDED FOR .env SUPPORT

# ✅ CLOUDINARY IMPORT ADDED
import cloudinary
import cloudinary.uploader
import cloudinary.api  # ✅ ADDED FOR FETCHING

# ==================== ENHANCED LOGGING FOR RENDER ====================
# Color codes for terminal
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def log_success(message):
    """Green success message for Render logs"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} {Colors.GREEN}{Colors.BOLD}✅ {message}{Colors.END}")

def log_info(message):
    """Blue info message for Render logs"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} {Colors.BLUE}{Colors.BOLD}📘 {message}{Colors.END}")

def log_warning(message):
    """Yellow warning message for Render logs"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} {Colors.YELLOW}{Colors.BOLD}⚠️ {message}{Colors.END}")

def log_error(message):
    """Red error message for Render logs"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} {Colors.RED}{Colors.BOLD}❌ {message}{Colors.END}")

def log_step(message):
    """Step header message for Render logs"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} {Colors.BOLD}🚀 {message}{Colors.END}")

def log_divider():
    """Print divider line for Render logs"""
    divider = "=" * 60
    print(f"{Colors.BOLD}{divider}{Colors.END}")

# ✅ Load environment variables from .env file (local development ke liye)
load_dotenv()

# ==================== APPLICATION STARTUP LOG ====================
log_divider()
log_step("🚀 STARTING BITE ME BUDDY APPLICATION")
log_divider()

app = Flask(__name__, 
    template_folder='templates',  # ✅ Explicit template folder
    static_folder='static',       # ✅ Explicit static folder
    static_url_path='/static'     # ✅ ADDED FOR RENDER
)

# Secret key setup
secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.secret_key = secret_key
log_info(f"App secret key: {'Set' if secret_key != 'dev-secret-key-change-in-production' else 'Using default (change in production)'}")

# ✅ CLOUDINARY CONFIGURATION ADDED
cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
api_key = os.environ.get("CLOUDINARY_API_KEY")
api_secret = os.environ.get("CLOUDINARY_API_SECRET")

if cloud_name and api_key and api_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )
    log_success("Cloudinary configured successfully")
else:
    log_warning("Cloudinary credentials not set - image uploads will not work")

# Default avatar URL (Cloudinary pe upload karna hoga)
DEFAULT_AVATAR_URL = "https://res.cloudinary.com/demo/image/upload/v1234567890/profile_pics/default-avatar.png"

# ✅ CLOUDINARY FOLDERS FOR SERVICES AND MENU
SERVICES_FOLDER = "services"
MENU_FOLDER = "menu_items"

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists (local development ke liye)
if os.environ.get('RENDER') is None:  # Local development only
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== DATABASE FUNCTIONS WITH RENDER LOGS ====================
def get_db_connection():
    """Establish database connection using DATABASE_URL from environment"""
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        log_error("DATABASE_URL environment variable is not set")
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Parse DATABASE_URL for psycopg
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Log connection info (sensitive info hide karenge)
    safe_url = database_url.split('@')[-1] if '@' in database_url else database_url
    log_info(f"Connecting to database: postgresql://...@{safe_url}")
    
    try:
        conn = psycopg.connect(database_url, row_factory=dict_row)
        log_success("Database connection established")
        return conn
    except Exception as e:
        log_error(f"Database connection failed: {str(e)}")
        raise

def create_all_tables():
    """Create all database tables with detailed logging for Render"""
    start_time = time.time()
    
    try:
        log_divider()
        log_step("DATABASE INITIALIZATION STARTED")
        log_divider()
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                
                # ====================== USERS TABLE ======================
                log_info("Creating users table...")
                cur.execute('''
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
                ''')
                log_success("Users table created/verified")
                
                # ====================== SERVICES TABLE ======================
                log_info("Creating services table...")
                cur.execute('''
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
                ''')
                log_success("Services table created/verified")
                
                # ====================== MENU TABLE ======================
                log_info("Creating menu table...")
                cur.execute('''
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
                ''')
                log_success("Menu table created/verified")
                
                # ====================== CART TABLE ======================
                log_info("Creating cart table...")
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS cart (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        item_type VARCHAR(10) CHECK (item_type IN ('service', 'menu')),
                        item_id INTEGER NOT NULL,
                        quantity INTEGER DEFAULT 1,
                        UNIQUE(user_id, item_type, item_id)
                    )
                ''')
                log_success("Cart table created/verified")
                
                # ====================== ORDERS TABLE ======================
                log_info("Creating orders table...")
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS orders (
                        order_id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        total_amount DECIMAL(10, 2) NOT NULL,
                        payment_mode VARCHAR(20) NOT NULL,
                        delivery_location TEXT NOT NULL,
                        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status VARCHAR(20) DEFAULT 'pending'
                    )
                ''')
                log_success("Orders table created/verified")
                
                # ====================== ORDER ITEMS TABLE ======================
                log_info("Creating order_items table...")
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS order_items (
                        order_item_id SERIAL PRIMARY KEY,
                        order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
                        item_type VARCHAR(10) CHECK (item_type IN ('service', 'menu')),
                        item_id INTEGER NOT NULL,
                        quantity INTEGER NOT NULL,
                        price DECIMAL(10, 2) NOT NULL
                    )
                ''')
                log_success("Order items table created/verified")
                
                # ====================== CREATE INDEXES ======================
                log_info("Creating database indexes...")
                
                indexes = [
                    ("idx_cart_user_id", "cart(user_id)"),
                    ("idx_orders_user_id", "orders(user_id)"),
                    ("idx_order_items_order_id", "order_items(order_id)"),
                    ("idx_services_status", "services(status)"),
                    ("idx_menu_status", "menu(status)"),
                    ("idx_users_phone", "users(phone)"),
                    ("idx_users_email", "users(email)")
                ]
                
                for idx_name, idx_def in indexes:
                    try:
                        cur.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}')
                        log_success(f"Index {idx_name} created")
                    except Exception as idx_error:
                        log_warning(f"Index {idx_name}: {str(idx_error)}")
                
                conn.commit()
                
                # ====================== ADD SAMPLE DATA ======================
                log_info("Checking for sample data...")
                added_services = add_sample_services_if_empty(cur)
                added_menu = add_sample_menu_if_empty(cur)
                
                if added_services or added_menu:
                    conn.commit()
                    log_success("Sample data added successfully")
                
                # ====================== VERIFICATION ======================
                log_info("Verifying all tables...")
                tables = ['users', 'services', 'menu', 'cart', 'orders', 'order_items']
                all_tables_exist = True
                
                for table in tables:
                    cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")
                    exists = cur.fetchone()['exists']
                    
                    if exists:
                        cur.execute(f"SELECT COUNT(*) as count FROM {table}")
                        count = cur.fetchone()['count']
                        log_success(f"Table '{table}': {count} records")
                    else:
                        log_error(f"Table '{table}' NOT FOUND")
                        all_tables_exist = False
                
                elapsed_time = time.time() - start_time
                
                if all_tables_exist:
                    log_divider()
                    log_success(f"DATABASE INITIALIZATION COMPLETED IN {elapsed_time:.2f} SECONDS")
                    log_divider()
                    return True
                else:
                    log_error("Database initialization incomplete - some tables missing")
                    return False
                
    except Exception as e:
        elapsed_time = time.time() - start_time
        log_error(f"Database initialization failed after {elapsed_time:.2f} seconds")
        log_error(f"Error details: {str(e)}")
        traceback.print_exc()
        raise

def add_sample_services_if_empty(cur):
    """Add sample services data if table is empty"""
    cur.execute("SELECT COUNT(*) as count FROM services")
    services_count = cur.fetchone()['count']
    
    if services_count == 0:
        log_info("Adding sample services data...")
        sample_services = [
            ('Home Cleaning', 500.00, 50.00, 450.00, 'Professional home cleaning service', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg'),
            ('Car Wash', 300.00, 30.00, 270.00, 'Complete car washing and detailing', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service2.jpg'),
            ('Plumbing', 800.00, 80.00, 720.00, 'Plumbing repair and maintenance', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service3.jpg'),
            ('Electrician', 600.00, 60.00, 540.00, 'Electrical repairs and installations', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service4.jpg'),
            ('Gardening', 400.00, 40.00, 360.00, 'Garden maintenance and landscaping', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service5.jpg')
        ]
        
        for service in sample_services:
            cur.execute(
                "INSERT INTO services (name, price, discount, final_price, description, photo) VALUES (%s, %s, %s, %s, %s, %s)",
                service
            )
        log_success(f"Added {len(sample_services)} sample services")
        return True
    return False

def add_sample_menu_if_empty(cur):
    """Add sample menu items data if table is empty"""
    cur.execute("SELECT COUNT(*) as count FROM menu")
    menu_count = cur.fetchone()['count']
    
    if menu_count == 0:
        log_info("Adding sample menu items data...")
        sample_menu = [
            ('Pizza Margherita', 250.00, 25.00, 225.00, 'Delicious cheese pizza with toppings', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_food.jpg'),
            ('Chicken Burger', 120.00, 12.00, 108.00, 'Juicy burger with veggies and sauce', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_food2.jpg'),
            ('Pasta Alfredo', 180.00, 18.00, 162.00, 'Italian pasta with creamy sauce', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_food3.jpg'),
            ('Caesar Salad', 150.00, 15.00, 135.00, 'Fresh vegetable salad with dressing', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_food4.jpg'),
            ('Chocolate Brownie', 80.00, 8.00, 72.00, 'Warm brownie with ice cream', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_food5.jpg')
        ]
        
        for item in sample_menu:
            cur.execute(
                "INSERT INTO menu (name, price, discount, final_price, description, photo) VALUES (%s, %s, %s, %s, %s, %s)",
                item
            )
        log_success(f"Added {len(sample_menu)} sample menu items")
        return True
    return False

def verify_tables_exist():
    """Verify that all required tables exist and are accessible"""
    try:
        required_tables = ['users', 'services', 'menu', 'cart', 'orders', 'order_items']
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for table in required_tables:
                    cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')")
                    exists = cur.fetchone()['exists']
                    
                    if not exists:
                        log_error(f"Table '{table}' does not exist!")
                        return False
                    else:
                        log_info(f"Table '{table}' verified!")
                
                log_success("All database tables verified successfully!")
                return True
                
    except Exception as e:
        log_error(f"Database verification failed: {str(e)}")
        return False

# ==================== APPLICATION INITIALIZATION ====================
def initialize_application():
    """Initialize the entire application with proper logging for Render"""
    log_divider()
    log_step("APPLICATION INITIALIZATION STARTED")
    log_divider()
    
    # Check environment variables
    log_info("Checking environment variables...")
    env_vars = {
        'DATABASE_URL': os.environ.get('DATABASE_URL'),
        'SECRET_KEY': os.environ.get('SECRET_KEY'),
        'CLOUDINARY_CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
        'CLOUDINARY_API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
        'CLOUDINARY_API_SECRET': os.environ.get('CLOUDINARY_API_SECRET')
    }
    
    for key, value in env_vars.items():
        if value:
            masked_value = '***' + value[-4:] if len(value) > 8 else '***'
            log_success(f"{key}: {masked_value}")
        else:
            log_warning(f"{key}: Not set")
    
    # Initialize database
    try:
        log_info("Starting database initialization...")
        if create_all_tables():
            log_success("Database initialization successful!")
        else:
            log_error("Database initialization failed!")
            return False
    except Exception as e:
        log_error(f"Database initialization error: {str(e)}")
        return False
    
    # Check static files
    log_info("Checking static files...")
    if os.path.exists('static'):
        log_success("Static folder exists")
    else:
        log_warning("Static folder not found - creating...")
        os.makedirs('static', exist_ok=True)
    
    if os.path.exists('templates'):
        log_success("Templates folder exists")
    else:
        log_error("Templates folder not found!")
        return False
    
    log_divider()
    log_success("APPLICATION INITIALIZATION COMPLETED")
    log_divider()
    return True

# Database initialization on app startup
@app.before_first_request
def initialize_database_on_startup():
    """Initialize database before first request"""
    try:
        log_info("🚀 App starting - initializing database...")
        
        # First, try to verify if tables exist
        if not verify_tables_exist():
            # If tables don't exist, create them
            log_info("Creating missing tables...")
            create_all_tables()
        else:
            log_info("Database tables already exist. Skipping creation.")
            
    except Exception as e:
        log_error(f"Failed to initialize database: {str(e)}")
        # Don't crash the app, but log the error

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

# ==================== HEALTH CHECK AND ADMIN ROUTES ====================
@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    try:
        # Try database connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return jsonify({
            'status': 'healthy',
            'service': 'Bite Me Buddy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        log_error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/db-status')
def db_status():
    """Check database status with detailed info"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                tables = ['users', 'services', 'menu', 'cart', 'orders', 'order_items']
                status = {}
                
                for table in tables:
                    cur.execute(f"SELECT COUNT(*) as count FROM {table}")
                    count = cur.fetchone()['count']
                    status[table] = count
                
                return jsonify({
                    'success': True,
                    'status': 'connected',
                    'tables': status,
                    'timestamp': datetime.now().isoformat(),
                    'message': 'Database is operational'
                })
    except Exception as e:
        log_error(f"DB status check failed: {str(e)}")
        return jsonify({
            'success': False,
            'status': 'disconnected',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'message': 'Database connection failed'
        }), 500

@app.route('/api/init-db')
def init_db_endpoint():
    """Manually initialize database via API"""
    try:
        success = create_all_tables()
        return jsonify({
            'success': success,
            'message': 'Database initialized successfully' if success else 'Database initialization failed',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        log_error(f"Manual DB init failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'message': 'Database initialization error'
        }), 500

# ==================== YOUR EXISTING ROUTES ====================
# (Yeh sabhi aapke existing routes yahin rahenge, maine sirf Render logging add kiya hai)

@app.route('/')
def home():
    """Home page - redirect to login or dashboard"""
    log_info(f"Home page accessed - User in session: {'user_id' in session}")
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration with profile picture upload"""
    if request.method == 'POST':
        log_info(f"New registration attempt - Phone: {request.form.get('phone', '')}")
        # ... existing registration code from your app.py ...
        # Get form data
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
        
        # ✅ CLOUDINARY PROFILE PICTURE HANDLING - UPDATED
        profile_pic = DEFAULT_AVATAR_URL
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                try:
                    # ✅ Upload to Cloudinary
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
                    log_success(f"Profile picture uploaded to Cloudinary: {profile_pic[:50]}...")
                    
                except Exception as e:
                    flash(f'Profile photo upload failed: {str(e)}', 'warning')
                    log_warning(f"Profile picture upload failed: {str(e)}")
                    # Fallback to default avatar
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
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Check if phone or email already exists
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
                    user_id = cur.fetchone()['id']
                    conn.commit()
                    
                    # Set session
                    session['user_id'] = user_id
                    session['full_name'] = full_name
                    session['phone'] = phone
                    session['email'] = email
                    session['location'] = location
                    session['profile_pic'] = profile_pic
                    
                    # ALSO SET created_at IN SESSION FOR NEW USER
                    session['created_at'] = datetime.now().strftime('%d %b %Y')
                    
                    log_success(f"User registered successfully: {full_name} (ID: {user_id})")
                    flash('Registration successful!', 'success')
                    return redirect(url_for('dashboard'))
                    
        except Exception as e:
            log_error(f"Registration failed: {str(e)}")
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login with mobile number and password"""
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        log_info(f"Login attempt - Phone: {phone}")
        
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
                        # Set session
                        session['user_id'] = user['id']
                        session['full_name'] = user['full_name']
                        session['phone'] = user['phone']
                        session['email'] = user['email']
                        session['location'] = user['location']
                        session['profile_pic'] = user['profile_pic']
                        
                        # Add created_at to session (date formatting)
                        if user.get('created_at'):
                            created_at = user['created_at']
                            # Format date: "03 Jan 2026"
                            try:
                                # PostgreSQL timestamp format
                                if isinstance(created_at, str):
                                    created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                                formatted_date = created_at.strftime('%d %b %Y')
                                session['created_at'] = formatted_date
                            except Exception as date_error:
                                # If formatting fails, use raw date
                                session['created_at'] = str(created_at).split()[0] if created_at else 'Recently'
                        else:
                            session['created_at'] = 'Recently'
                        
                        log_success(f"User logged in: {user['full_name']} (ID: {user['id']})")
                        flash('Login successful!', 'success')
                        return redirect(url_for('dashboard'))
                    else:
                        log_warning(f"Failed login attempt for phone: {phone}")
                        flash('Invalid phone number or password', 'error')
                        return render_template('login.html')
                        
        except Exception as e:
            log_error(f"Login failed: {str(e)}")
            flash(f'Login failed: {str(e)}', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user and clear session"""
    if 'user_id' in session:
        log_info(f"User logging out: {session.get('full_name', 'Unknown')}")
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with navigation"""
    log_info(f"Dashboard accessed by: {session.get('full_name', 'Unknown')}")
    return render_template('dashboard.html')

@app.route('/services')
@login_required
def services():
    """Display active services - UPDATED TO USE CLOUDINARY"""
    try:
        log_info(f"Services page accessed by user: {session['user_id']}")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Fetch services from database
                cur.execute(
                    "SELECT * FROM services WHERE status = 'active' ORDER BY name"
                )
                services_list = cur.fetchall()
        
        # ✅ CLOUDINARY INTEGRATION FOR SERVICES
        try:
            # Get all images from Cloudinary services folder
            cloudinary_services = cloudinary.api.resources(
                type="upload",
                prefix=SERVICES_FOLDER,
                max_results=100
            )
            
            # Create a mapping of service names to Cloudinary URLs
            cloudinary_images = {}
            for resource in cloudinary_services.get('resources', []):
                # Extract service name from filename (remove folder and extension)
                filename = os.path.splitext(os.path.basename(resource['public_id']))[0]
                service_name = filename.replace('_', ' ').title()
                cloudinary_images[service_name.lower()] = resource['secure_url']
            
            # Update services list with Cloudinary images if available
            for service in services_list:
                service_name = service['name'].lower()
                if service_name in cloudinary_images:
                    service['photo'] = cloudinary_images[service_name]
                elif not service.get('photo'):
                    # Use a default service image from Cloudinary
                    service['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
                    
        except Exception as cloudinary_error:
            log_warning(f"Cloudinary error for services: {cloudinary_error}")
            # If Cloudinary fails, keep existing images
            
        return render_template('services.html', services=services_list)
    except Exception as e:
        log_error(f"Error loading services: {str(e)}")
        flash(f'Error loading services: {str(e)}', 'error')
        return render_template('services.html', services=[])

@app.route('/menu')
@login_required
def menu():
    """Display active menu items - UPDATED TO USE CLOUDINARY"""
    try:
        log_info(f"Menu page accessed by user: {session['user_id']}")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM menu WHERE status = 'active' ORDER BY name"
                )
                menu_items = cur.fetchall()
        
        # ✅ CLOUDINARY INTEGRATION FOR MENU ITEMS
        try:
            # Get all images from Cloudinary menu folder
            cloudinary_menu = cloudinary.api.resources(
                type="upload",
                prefix=MENU_FOLDER,
                max_results=100
            )
            
            # Create a mapping of menu item names to Cloudinary URLs
            cloudinary_images = {}
            for resource in cloudinary_menu.get('resources', []):
                # Extract menu name from filename (remove folder and extension)
                filename = os.path.splitext(os.path.basename(resource['public_id']))[0]
                menu_name = filename.replace('_', ' ').title()
                cloudinary_images[menu_name.lower()] = resource['secure_url']
            
            # Update menu list with Cloudinary images if available
            for menu_item in menu_items:
                item_name = menu_item['name'].lower()
                if item_name in cloudinary_images:
                    menu_item['photo'] = cloudinary_images[item_name]
                elif not menu_item.get('photo'):
                    # Use a default menu image from Cloudinary
                    menu_item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_food.jpg"
                    
        except Exception as cloudinary_error:
            log_warning(f"Cloudinary error for menu: {cloudinary_error}")
            # If Cloudinary fails, keep existing images
            
        return render_template('menu.html', menu_items=menu_items)
    except Exception as e:
        log_error(f"Error loading menu: {str(e)}")
        flash(f'Error loading menu: {str(e)}', 'error')
        return render_template('menu.html', menu_items=[])

# ... aapke baaki routes yahin rahenge (cart, checkout, orders, profile, etc.) ...
# Maine sirf logging add kiya hai, actual functionality same hai

# ==================== CLOUDINARY PROFILE PICTURE UPLOAD ====================
@app.route('/upload-profile-pic', methods=['POST'])
@login_required
def upload_profile_pic():
    """Upload profile picture to Cloudinary with proper transformations"""
    try:
        log_info(f"Profile picture upload requested by user: {session['user_id']}")
        
        if 'profile_pic' not in request.files:
            return jsonify({'success': False, 'message': 'No file provided'})
        
        file = request.files['profile_pic']
        
        if not file or file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'Invalid file type. Allowed: png, jpg, jpeg, gif'})
        
        # Generate unique public_id using user_id
        public_id = f"profile_pic_{session['user_id']}_{secrets.token_hex(8)}"
        
        # ✅ UPLOAD TO CLOUDINARY WITH PROPER TRANSFORMATIONS
        try:
            upload_result = cloudinary.uploader.upload(
                file,
                folder="profile_pics",
                public_id=public_id,
                overwrite=True,
                transformation=[
                    {
                        'width': 500,
                        'height': 500,
                        'crop': 'fill'
                    },
                    {
                        'quality': 'auto',
                        'fetch_format': 'auto'
                    }
                ]
            )
            
            # Get the secure URL from the upload result
            uploaded_url = upload_result.get('secure_url')
            
            if not uploaded_url:
                return jsonify({'success': False, 'message': 'Upload failed - no URL returned'})
            
            # Update the user's profile picture in database
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE users SET profile_pic = %s WHERE id = %s",
                        (uploaded_url, session['user_id'])
                    )
                    conn.commit()
            
            # Update session
            session['profile_pic'] = uploaded_url
            
            log_success(f"Profile picture updated for user {session['user_id']}")
            return jsonify({
                'success': True,
                'url': uploaded_url,
                'message': 'Profile picture updated successfully'
            })
            
        except Exception as upload_error:
            log_error(f"Cloudinary upload error: {str(upload_error)}")
            return jsonify({
                'success': False, 
                'message': f'Upload failed: {str(upload_error)}'
            })
            
    except Exception as e:
        log_error(f"General error in upload_profile_pic: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error: {str(e)}'
        })

# ==================== MAIN EXECUTION ====================
if __name__ == '__main__':
    # Check if running on Render
    is_render = os.environ.get('RENDER') is not None
    
    if not is_render:
        # Local development - initialize database on startup
        log_divider()
        log_step("LOCAL DEVELOPMENT MODE")
        log_divider()
        
        # Initialize application
        init_success = initialize_application()
        
        if not init_success:
            log_error("Application initialization failed!")
            log_info("Server will start but some features may not work")
        
        # Server information
        port = int(os.environ.get('PORT', 5000))
        host = '0.0.0.0'
        
        log_info(f"Server configured on port: {port}")
        log_info(f"Host: {host}")
        log_info(f"Debug mode: {app.debug}")
        
        log_divider()
        log_success("SERVER IS READY TO ACCEPT CONNECTIONS")
        log_info(f"👉 Local URL: http://localhost:{port}")
        log_info(f"👉 Health check: http://localhost:{port}/health")
        log_info(f"👉 DB status: http://localhost:{port}/api/db-status")
        log_divider()
        
        # Start Flask development server
        try:
            app.run(debug=True, host=host, port=port)
        except Exception as e:
            log_error(f"Server failed to start: {str(e)}")
            sys.exit(1)
    else:
        # On Render, gunicorn will run the app
        log_divider()
        log_step("RENDER PRODUCTION MODE")
        log_divider()
        
        # Initialize application on Render
        log_info("Initializing application for Render...")
        init_success = initialize_application()
        
        if init_success:
            log_success("Application initialized successfully!")
        else:
            log_error("Application initialization failed!")
        
        log_divider()
        log_success("✅ APPLICATION READY FOR GUNICORN")
        log_info("👉 Health check endpoint: /health")
        log_info("👉 Database status: /api/db-status")
        log_info("👉 Manual DB init: /api/init-db")
        log_divider()
        # The app will be served by gunicorn via Procfile
