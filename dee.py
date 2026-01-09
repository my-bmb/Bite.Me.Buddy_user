# app.py - COMPLETELY FIXED CLOUDINARY TRANSFORMATION ERROR
# WITH ADDED LOADING PAGE FUNCTIONALITY
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
from dotenv import load_dotenv  # ✅ ADDED FOR .env SUPPORT
import time  # ✅ ADDED FOR LOADING PAGE
import threading  # ✅ ADDED FOR LOADING PAGE

# ✅ CLOUDINARY IMPORT ADDED
import cloudinary
import cloudinary.uploader
import cloudinary.api  # ✅ ADDED FOR FETCHING

# ✅ JSON IMPORT ADDED FOR ORDER STORAGE
import json

# ✅ Load environment variables from .env file (local development ke liye)
load_dotenv()

app = Flask(__name__, 
    template_folder='templates',  # ✅ Explicit template folder
    static_folder='static',       # ✅ Explicit static folder
    static_url_path='/static'     # ✅ ADDED FOR RENDER
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ✅ CLOUDINARY CONFIGURATION ADDED
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

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

# ✅ LOADING PAGE CONFIGURATION
app_start_time = time.time()
app_wakeup_time = app_start_time
app_just_woke_up = True  # Flag to track if app just woke up

# Ensure upload folder exists (local development ke liye)
if os.environ.get('RENDER') is None:  # Local development only
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """Establish database connection using DATABASE_URL from environment"""
    database_url = os.environ.get('DATABASE_URL')
    
    # Debug info (remove in production if needed)
    if os.environ.get('RENDER') is None:  # Only show in local
        print(f"🔗 Database URL: {database_url[:30]}..." if database_url and len(database_url) > 30 else f"🔗 Database URL: {database_url}")
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Parse DATABASE_URL for psycopg
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        conn = psycopg.connect(database_url, row_factory=dict_row)
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        raise

def init_database():
    """Initialize database tables if they don't exist"""
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
                    print("📦 Creating database tables...")
                    
                    # Users table
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
                    
                    # Services table
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
                    
                    # Menu table
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
                    
                    # Cart table
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
                    
                    # Orders table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS orders (
                            order_id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            items TEXT NOT NULL,                       -- ✅ JSON STORAGE
                            total_amount DECIMAL(10, 2) NOT NULL,
                            payment_mode VARCHAR(20) NOT NULL,
                            delivery_location TEXT NOT NULL,
                            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status VARCHAR(20) DEFAULT 'pending'
                        )
                    """)
                    
                    # Order items table
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
                    
                    # Create indexes for better performance
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_services_status ON services(status)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_menu_status ON menu(status)")
                    
                    print("✅ Tables created successfully!")
                else:
                    print("✅ Tables already exist, skipping creation")
                
                # Insert sample data for services if table is empty
                cur.execute("SELECT COUNT(*) as count FROM services")
                services_count = cur.fetchone()['count']
                
                if services_count == 0:
                    print("📝 Adding sample services...")
                    sample_services = [
                        ('Home Cleaning', 500.00, 50.00, 450.00, 'Professional home cleaning service'),
                        ('Car Wash', 300.00, 30.00, 270.00, 'Complete car washing and detailing'),
                        ('Plumbing', 800.00, 80.00, 720.00, 'Plumbing repair and maintenance'),
                        ('Electrician', 600.00, 60.00, 540.00, 'Electrical repairs and installations'),
                        ('Gardening', 400.00, 40.00, 360.00, 'Garden maintenance and landscaping')
                    ]
                    
                    for service in sample_services:
                        cur.execute("""
                            INSERT INTO services (name, price, discount, final_price, description)
                            VALUES (%s, %s, %s, %s, %s)
                        """, service)
                    print(f"✅ Added {len(sample_services)} sample services")
                
                # Insert sample data for menu if table is empty
                cur.execute("SELECT COUNT(*) as count FROM menu")
                menu_count = cur.fetchone()['count']
                
                if menu_count == 0:
                    print("📝 Adding sample menu items...")
                    sample_menu = [
                        ('Pizza', 250.00, 25.00, 225.00, 'Delicious cheese pizza with toppings'),
                        ('Burger', 120.00, 12.00, 108.00, 'Juicy burger with veggies and sauce'),
                        ('Pasta', 180.00, 18.00, 162.00, 'Italian pasta with creamy sauce'),
                        ('Salad', 150.00, 15.00, 135.00, 'Fresh vegetable salad with dressing'),
                        ('Ice Cream', 80.00, 8.00, 72.00, 'Vanilla ice cream with chocolate sauce')
                    ]
                    
                    for item in sample_menu:
                        cur.execute("""
                            INSERT INTO menu (name, price, discount, final_price, description)
                            VALUES (%s, %s, %s, %s, %s)
                        """, item)
                    print(f"✅ Added {len(sample_menu)} sample menu items")
                
                conn.commit()
                print("✅ Database initialization completed successfully!")
                
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        raise

# ✅ AUTOMATIC DATABASE INITIALIZATION ON STARTUP
print("🚀 Starting Bite Me Buddy Application...")
try:
    init_database()
    print("✅ Database initialization completed on startup!")
except Exception as e:
    print(f"⚠️ Database initialization failed: {e}")
    print("⚠️ You may need to run '/init-db' manually")

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

# ============================================
# ✅ LOADING PAGE ROUTES (NEW ADDITION)
# ============================================

@app.route('/loading')
def loading_page():
    """Loading/wake-up page for Render free plan"""
    return render_template('loading.html')

@app.route('/health')
def health_check():
    """Health check endpoint for Render and loading page"""
    try:
        # Try database connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        
        uptime = time.time() - app_start_time
        
        return jsonify({
            'status': 'healthy',
            'service': 'Bite Me Buddy',
            'database': 'connected',
            'uptime': round(uptime, 2),
            'wakeup_time': app_wakeup_time,
            'is_ready': uptime > 30,  # Consider app ready after 30 seconds
            'redirect_to': '/dashboard' if 'user_id' in session else '/login',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/ready')
def api_ready():
    """API endpoint for loading page to check if app is fully ready"""
    uptime = time.time() - app_start_time
    is_ready = uptime > 30  # Consider app ready after 30 seconds
    
    return jsonify({
        'ready': is_ready,
        'uptime': uptime,
        'redirect_to': '/dashboard' if 'user_id' in session else '/login',
        'timestamp': datetime.now().isoformat()
    })

# ============================================
# ✅ MAIN INDEX ROUTE - UPDATED FOR LOADING PAGE
# ============================================

@app.route('/')
def home():
    """Home page - show loading page first, then auto-redirect"""
    # If user is already logged in, check if we need loading page
    if 'user_id' in session:
        # Check if app just woke up (less than 2 minutes ago)
        uptime = time.time() - app_start_time
        
        if uptime < 120 and app_just_woke_up:
            # App just woke up, show loading page
            print(f"🔄 App woke up recently ({uptime:.1f}s), showing loading page")
            return render_template('loading.html')
        else:
            # App is already awake or user returning, go to dashboard
            return redirect(url_for('dashboard'))
    else:
        # User not logged in
        uptime = time.time() - app_start_time
        
        if uptime < 120 and app_just_woke_up:
            # App just woke up, show loading page
            print(f"🔄 App woke up recently ({uptime:.1f}s), showing loading page for new user")
            return render_template('loading.html')
        else:
            # App already awake, go to login
            return redirect(url_for('login'))

# ============================================
# ✅ BACKGROUND TASK FOR APP WAKE-UP (NEW)
# ============================================

def mark_app_awake():
    """Background task to mark app as fully awake after some time"""
    global app_just_woke_up
    # Wait 60 seconds before marking app as fully awake
    time.sleep(60)
    app_just_woke_up = False
    global app_wakeup_time
    app_wakeup_time = time.time()
    print(f"[{datetime.now()}] App marked as fully awake at {app_wakeup_time}")

# Start background thread when app starts
def initialize_background_tasks():
    """Initialize background tasks for loading page"""
    threading.Thread(target=mark_app_awake, daemon=True).start()
    print(f"[{datetime.now()}] Background tasks initialized. App start time: {app_start_time}")

# ✅ DATABASE INITIALIZATION ROUTE (MANUAL TRIGGER)
@app.route('/init-db')
def init_db_route():
    """Manual database initialization endpoint"""
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
# ✅ CLOUDINARY PROFILE PICTURE UPLOAD ROUTE
# ============================================

@app.route('/upload-profile-pic', methods=['POST'])
@login_required
def upload_profile_pic():
    """Upload profile picture to Cloudinary with proper transformations"""
    try:
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
        # Using list of dictionaries format as required by Python SDK
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
            
            return jsonify({
                'success': True,
                'url': uploaded_url,
                'message': 'Profile picture updated successfully'
            })
            
        except Exception as upload_error:
            print(f"Cloudinary upload error: {str(upload_error)}")
            return jsonify({
                'success': False, 
                'message': f'Upload failed: {str(upload_error)}'
            })
            
    except Exception as e:
        print(f"General error in upload_profile_pic: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error: {str(e)}'
        })

# ============================================
# APP.PY KE CLOUDINARY ROUTES YAHAN SE SHURU
# ============================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration with profile picture upload"""
    if request.method == 'POST':
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
        
        # ✅ CLOUDINARY PROFILE PICTURE HANDLING - UPDATED (FROM APP.PY)
        profile_pic = DEFAULT_AVATAR_URL
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                try:
                    # ✅ Upload to Cloudinary (APP.PY KA CODE)
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
                    
                    flash('Registration successful!', 'success')
                    return redirect(url_for('dashboard'))
                    
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login with mobile number and password"""
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
    """Logout user and clear session"""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with navigation"""
    return render_template('dashboard.html')

@app.route('/services')
@login_required
def services():
    """Display active services - UPDATED TO USE CLOUDINARY (FROM APP.PY)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Fetch services from database
                cur.execute(
                    "SELECT * FROM services WHERE status = 'active' ORDER BY name"
                )
                services_list = cur.fetchall()
        
        # ✅ CLOUDINARY INTEGRATION FOR SERVICES (APP.PY KA CODE)
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
            print(f"Cloudinary error for services: {cloudinary_error}")
            # If Cloudinary fails, keep existing images
            
        return render_template('services.html', services=services_list)
    except Exception as e:
        flash(f'Error loading services: {str(e)}', 'error')
        return render_template('services.html', services=[])

@app.route('/menu')
@login_required
def menu():
    """Display active menu items - UPDATED TO USE CLOUDINARY (FROM APP.PY)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM menu WHERE status = 'active' ORDER BY name"
                )
                menu_items = cur.fetchall()
        
        # ✅ CLOUDINARY INTEGRATION FOR MENU ITEMS (APP.PY KA CODE)
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
            print(f"Cloudinary error for menu: {cloudinary_error}")
            # If Cloudinary fails, keep existing images
            
        return render_template('menu.html', menu_items=menu_items)
    except Exception as e:
        flash(f'Error loading menu: {str(e)}', 'error')
        return render_template('menu.html', menu_items=[])

@app.route('/cart')
@login_required
def cart():
    """Display user's cart"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get cart items with details
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
                
        return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)
    except Exception as e:
        flash(f'Error loading cart: {str(e)}', 'error')
        return render_template('cart.html', cart_items=[], total_amount=0)

@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    """Add item to cart"""
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
                # Check if item exists and is active
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
                
                # Check if item already in cart
                cur.execute("""
                    SELECT id, quantity FROM cart 
                    WHERE user_id = %s AND item_type = %s AND item_id = %s
                """, (session['user_id'], item_type, item_id))
                
                existing = cur.fetchone()
                
                if existing:
                    # Update quantity
                    new_quantity = existing['quantity'] + quantity
                    cur.execute("""
                        UPDATE cart SET quantity = %s 
                        WHERE id = %s
                    """, (new_quantity, existing['id']))
                else:
                    # Add new item
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
    """Update cart item quantity"""
    cart_id = request.form.get('cart_id')
    action = request.form.get('action')  # 'increase' or 'decrease'
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get current quantity
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
                    # Remove item from cart
                    cur.execute(
                        "DELETE FROM cart WHERE id = %s",
                        (cart_id,)
                    )
                else:
                    # Update quantity
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
    """Remove item from cart"""
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
# ✅ UPDATED CHECKOUT ROUTE WITH ITEMS JSON
# ============================================

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Order checkout and confirmation - UPDATED WITH ITEMS JSON"""
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
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Get cart items and calculate total - UPDATED TO GET ITEM DETAILS
                    cur.execute("""
                        SELECT c.item_type, c.item_id, c.quantity,
                               COALESCE(s.name, m.name) as item_name,
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
                    
                    # Calculate total amount
                    total_amount = sum(float(item['price']) * item['quantity'] for item in cart_items)
                    
                    # ✅ CREATE ITEMS JSON FOR STORAGE
                    items_json = json.dumps([
                        {
                            'item_type': item['item_type'],
                            'item_id': item['item_id'],
                            'item_name': item['item_name'],
                            'quantity': item['quantity'],
                            'price': float(item['price'])
                        }
                        for item in cart_items
                    ], indent=2)
                    
                    # ✅ CREATE ORDER WITH ITEMS JSON
                    cur.execute("""
                        INSERT INTO orders 
                        (user_id, items, total_amount, payment_mode, delivery_location, status)
                        VALUES (%s, %s, %s, %s, %s, 'pending')
                        RETURNING order_id
                    """, (session['user_id'], items_json, total_amount, payment_mode, delivery_location))
                    
                    order = cur.fetchone()
                    order_id = order['order_id']
                    
                    # ✅ CREATE ORDER ITEMS FOR DETAILED RECORDS
                    for item in cart_items:
                        cur.execute("""
                            INSERT INTO order_items 
                            (order_id, item_type, item_id, quantity, price)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (order_id, item['item_type'], item['item_id'], 
                              item['quantity'], item['price']))
                    
                    # Clear cart
                    cur.execute(
                        "DELETE FROM cart WHERE user_id = %s",
                        (session['user_id'],)
                    )
                    
                    conn.commit()  # ✅ IMPORTANT: COMMIT TRANSACTION
                    
                    flash(f'Order #{order_id} placed successfully!', 'success')
                    return redirect(url_for('order_history'))
                    
        except Exception as e:
            flash(f'Error placing order: {str(e)}', 'error')
            return redirect(url_for('cart'))
    
    # GET request - show checkout form
    # Get cart total for checkout page
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT SUM(COALESCE(s.final_price, m.final_price) * c.quantity) as total
                    FROM cart c
                    LEFT JOIN services s ON c.item_type = 'service' AND c.item_id = s.id
                    LEFT JOIN menu m ON c.item_type = 'menu' AND c.item_id = m.id
                    WHERE c.user_id = %s
                """, (session['user_id'],))
                result = cur.fetchone()
                cart_total = float(result['total']) if result['total'] else 0.0
    except Exception as e:
        cart_total = 0.0
    
    return render_template('checkout.html', cart_total=cart_total)

# ============================================
# ✅ UPDATED ORDER HISTORY ROUTE WITH JSON PARSING
# ============================================

@app.route('/order_history')
@login_required
def order_history():
    """Display user's order history - UPDATED TO USE ITEMS JSON"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # ✅ GET ORDERS WITH ITEMS FROM JSON
                cur.execute("""
                    SELECT order_id, user_id, items, total_amount, 
                           payment_mode, delivery_location, status, order_date
                    FROM orders 
                    WHERE user_id = %s 
                    ORDER BY order_date DESC
                """, (session['user_id'],))
                
                orders = cur.fetchall()
                orders_list = []
                
                for order in orders:
                    # Parse items JSON
                    items_list = []
                    try:
                        items_data = json.loads(order['items'])
                        for item in items_data:
                            items_list.append({
                                'name': item.get('item_name', 'Unknown Item'),
                                'type': item.get('item_type', 'unknown'),
                                'quantity': item.get('quantity', 1),
                                'price': float(item.get('price', 0))
                            })
                    except (json.JSONDecodeError, TypeError):
                        # Fallback to order_items table if JSON parsing fails
                        cur.execute("""
                            SELECT oi.*, 
                                   COALESCE(s.name, m.name) as item_name,
                                   COALESCE(s.photo, m.photo) as item_photo
                            FROM order_items oi
                            LEFT JOIN services s ON oi.item_type = 'service' AND oi.item_id = s.id
                            LEFT JOIN menu m ON oi.item_type = 'menu' AND oi.item_id = m.id
                            WHERE oi.order_id = %s
                        """, (order['order_id'],))
                        
                        items_data = cur.fetchall()
                        for item in items_data:
                            items_list.append({
                                'name': item.get('item_name', 'Unknown Item'),
                                'type': item.get('item_type', 'unknown'),
                                'quantity': item.get('quantity', 1),
                                'price': float(item.get('price', 0))
                            })
                    
                    orders_list.append({
                        'order_id': order['order_id'],
                        'total_amount': float(order['total_amount']),
                        'payment_mode': order['payment_mode'],
                        'delivery_location': order['delivery_location'],
                        'status': order['status'],
                        'order_date': order['order_date'],
                        'items': items_list  # ✅ ITEMS LIST INCLUDED
                    })
                
        return render_template('orders.html', orders=orders_list)
    except Exception as e:
        flash(f'Error loading order history: {str(e)}', 'error')
        return render_template('orders.html', orders=[])

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile view and edit (FROM APP.PY)"""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        location = request.form.get('location', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validate inputs
        errors = []
        if not all([full_name, email, location]):
            errors.append('All fields except password are required')
        if '@' not in email:
            errors.append('Invalid email address')
        if new_password and len(new_password) < 6:
            errors.append('Password must be at least 6 characters')
        if new_password and new_password != confirm_password:
            errors.append('Passwords do not match')
        
        # ✅ CLOUDINARY PROFILE PICTURE HANDLING - UPDATED (FROM APP.PY)
        profile_pic = session.get('profile_pic', DEFAULT_AVATAR_URL)
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                try:
                    # ✅ Upload to Cloudinary (APP.PY KA CODE)
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
                    # Keep existing profile picture
                    profile_pic = session.get('profile_pic', DEFAULT_AVATAR_URL)
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('profile.html')
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Check if email already exists (excluding current user)
                    cur.execute(
                        "SELECT id FROM users WHERE email = %s AND id != %s",
                        (email, session['user_id'])
                    )
                    if cur.fetchone():
                        flash('Email already registered to another account', 'error')
                        return render_template('profile.html')
                    
                    # Prepare update query
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
                    
                    # Add password update if provided
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
                    session['location'] = location
                    session['profile_pic'] = profile_pic
                    
                    flash('Profile updated successfully!', 'success')
                    return redirect(url_for('profile'))
                    
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
            return render_template('profile.html')
    
    # GET request - show profile
    return render_template('profile.html')

@app.route('/get_service_details/<int:service_id>')
@login_required
def get_service_details(service_id):
    """Get service details for modal - UPDATED TO USE CLOUDINARY (FROM APP.PY)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM services WHERE id = %s AND status = 'active'",
                    (service_id,)
                )
                service = cur.fetchone()
                
                if service:
                    # ✅ CLOUDINARY: Try to get image from Cloudinary (APP.PY KA CODE)
                    service_name = service['name'].lower()
                    try:
                        # Search for service image in Cloudinary
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
                        print(f"Cloudinary error for service details: {cloudinary_error}")
                        # Keep existing photo if Cloudinary fails
                    
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
    """Get menu item details for modal - UPDATED TO USE CLOUDINARY (FROM APP.PY)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM menu WHERE id = %s AND status = 'active'",
                    (menu_id,)
                )
                menu_item = cur.fetchone()
                
                if menu_item:
                    # ✅ CLOUDINARY: Try to get image from Cloudinary (APP.PY KA CODE)
                    item_name = menu_item['name'].lower()
                    try:
                        # Search for menu image in Cloudinary
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
                        print(f"Cloudinary error for menu details: {cloudinary_error}")
                        # Keep existing photo if Cloudinary fails
                    
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
# FORGOT PASSWORD ROUTES - UPDATED WITH FIREBASE
# ============================================

@app.route('/forgot-password')
def forgot_password():
    """Display forgot password page with Firebase config"""
    # Pass Firebase config to template (hardcoded values)
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
    """Handle password reset after OTP verification"""
    try:
        # Get form data
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '').strip()
        
        # Basic validation
        if not mobile or not password:
            flash('Please fill all fields', 'error')
            return redirect('/forgot-password')
        
        # Validate mobile number format (ensure it starts with +)
        if not mobile.startswith('+'):
            # If it's 10 digits, add +91
            if mobile.isdigit() and len(mobile) == 10:
                mobile = '+91' + mobile
            else:
                flash('Please enter a valid mobile number with country code', 'error')
                return redirect('/forgot-password')
        
        # Generate hash for new password
        hashed_password = generate_password_hash(password)
        
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # First check if user exists with this mobile
                    # Note: Your database uses 'phone' column, not 'mobile'
                    cur.execute("SELECT id FROM users WHERE phone = %s", (mobile,))
                    user = cur.fetchone()
                    
                    if not user:
                        flash('Mobile number not registered', 'error')
                        return redirect('/forgot-password')
                    
                    # Update password
                    cur.execute(
                        "UPDATE users SET password = %s WHERE phone = %s",
                        (hashed_password, mobile)
                    )
                    
                    # Check if update was successful
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
# DATABASE MIGRATION FUNCTION (FOR EXISTING USERS)
# ============================================

def migrate_existing_users_to_cloudinary():
    """Migrate existing users' profile pics to Cloudinary - CORRECT TRANSFORMATION FORMAT"""
    print("🚀 Starting migration of existing profile pictures to Cloudinary...")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get all users with local profile pics
        cur.execute("""
            SELECT id, profile_pic 
            FROM users 
            WHERE profile_pic NOT LIKE 'http%' 
            AND profile_pic IS NOT NULL
            AND profile_pic != ''
        """)
        
        users = cur.fetchall()
        print(f"📊 Found {len(users)} users with local profile pictures")
        
        migrated_count = 0
        failed_count = 0
        
        for user in users:
            user_id = user['id']
            old_pic = user['profile_pic']
            
            # Check if file exists locally
            filepath = os.path.join('static', 'uploads', old_pic)
            
            if os.path.exists(filepath):
                try:
                    # ✅ CLOUDINARY UPLOAD WITH APP.PY FORMAT
                    with open(filepath, 'rb') as f:
                        result = cloudinary.uploader.upload(
                            f,
                            folder="profile_pics",
                            public_id=f"migrated_user_{user_id}",
                            overwrite=True,
                            transformation=[
                                {'width': 500, 'height': 500, 'crop': 'fill'},
                                {'quality': 'auto', 'fetch_format': 'auto'}
                            ]
                        )
                    
                    # Update database with Cloudinary URL
                    cur.execute(
                        "UPDATE users SET profile_pic = %s WHERE id = %s",
                        (result["secure_url"], user_id)
                    )
                    
                    print(f"✅ Migrated user {user_id}: {old_pic} → Cloudinary")
                    migrated_count += 1
                    
                except Exception as e:
                    print(f"❌ Failed to migrate user {user_id}: {str(e)}")
                    failed_count += 1
            else:
                print(f"⚠️  File not found for user {user_id}")
        
        # Also update users with default avatar to Cloudinary default
        print("\nUpdating default avatars to Cloudinary URL...")
        cur.execute("""
            UPDATE users 
            SET profile_pic = %s 
            WHERE profile_pic IS NULL 
            OR profile_pic = ''
            OR profile_pic = 'default-avatar.jpg'
            OR profile_pic LIKE '%default-avatar.png'
        """, (DEFAULT_AVATAR_URL,))
        
        default_updated = cur.rowcount
        print(f"Updated {default_updated} default avatars")
        
        conn.commit()
        conn.close()
        
        print("\n" + "="*50)
        print(f"📈 MIGRATION COMPLETE:")
        print(f"   Total users processed: {len(users)}")
        print(f"   ✅ Successfully migrated: {migrated_count}")
        print(f"   ❌ Failed: {failed_count}")
        print(f"   🔄 Default avatars updated: {default_updated}")
        print("="*50)
        
        return True
        
    except Exception as e:
        print(f"💥 Migration error: {str(e)}")
        return False

# ============================================
# APPLICATION STARTUP
# ============================================

if __name__ == '__main__':
    # Initialize background tasks for loading page
    initialize_background_tasks()
    
    # Check if running on Render
    is_render = os.environ.get('RENDER') is not None
    
    if not is_render:
        # Local development
        print("🚀 Starting in LOCAL DEVELOPMENT mode")
        try:
            print("✅ Database already initialized at startup!")
            
            # Optional: Run migration for existing users
            migrate_option = input("Run profile picture migration? (y/n): ")
            if migrate_option.lower() == 'y':
                migrate_existing_users_to_cloudinary()
                
        except Exception as e:
            print(f"⚠️  Error: {e}")
        
        # Create uploads directory if it doesn't exist
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Run Flask development server
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        # On Render, gunicorn will run the app
        print("🚀 Starting in RENDER PRODUCTION mode")
        print("✅ Application ready for gunicorn")
        print("✅ Loading page functionality activated")
        # The app will be served by gunicorn via Procfile