# app.py - COMPLETE FINAL VERSION
# Direct IST formatting - NO UTC to IST conversion issues
import os
from datetime import datetime, timedelta
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import base64
import io
from dotenv import load_dotenv

# ✅ SUPABASE IMPORTS
from supabase import create_client, Client
import postgrest

# ✅ CLOUDINARY IMPORTS
import cloudinary
import cloudinary.uploader
import cloudinary.api

# ✅ RAZORPAY IMPORTS
import razorpay
import hmac
import hashlib

# ✅ OTHER IMPORTS
import json
import requests
import time
import traceback
import pytz
from datetime import timezone
from functools import wraps
from dateutil import parser

# ✅ Load environment variables
load_dotenv()

# ✅ SUPABASE CONFIGURATION
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', SUPABASE_KEY)

# Initialize Supabase clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("✅ Supabase clients initialized successfully!")

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

# ✅ TIMEZONE CONFIGURATION
IST_TIMEZONE = pytz.timezone('Asia/Kolkata')
UTC_TIMEZONE = pytz.utc

# ============================================
# ✅ SIMPLE IST FORMATTING FUNCTIONS
# ============================================

def ist_now():
    """
    Returns current time in IST timezone
    """
    utc_now = datetime.now(UTC_TIMEZONE)
    return utc_now.astimezone(IST_TIMEZONE)

def format_ist_date_simple(date_value):
    """
    SUPER SIMPLE date formatter - directly converts any date to "DD MMM YYYY" format
    Example: "2026-02-12T10:30:00+00:00" → "12 Feb 2026"
    """
    if not date_value:
        return "Recently"
    
    try:
        # Convert to string
        date_str = str(date_value)
        print(f"📅 Raw date: {date_str}")
        
        # Case 1: ISO format with T (2026-02-12T10:30:00+00:00)
        if 'T' in date_str:
            date_part = date_str.split('T')[0]  # "2026-02-12"
            year, month, day = date_part.split('-')
            
            # Month names
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month_name = month_names[int(month) - 1]
            
            formatted = f"{int(day)} {month_name} {year}"
            print(f"✅ Formatted (ISO): {formatted}")
            return formatted
        
        # Case 2: Simple date format (2026-02-12)
        elif '-' in date_str and len(date_str) == 10:
            year, month, day = date_str.split('-')
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month_name = month_names[int(month) - 1]
            
            formatted = f"{int(day)} {month_name} {year}"
            print(f"✅ Formatted (Simple): {formatted}")
            return formatted
        
        # Case 3: Already formatted
        else:
            return date_str
            
    except Exception as e:
        print(f"❌ Date formatting error: {e}")
        return str(date_value)

def format_ist_datetime(datetime_obj, format_str="%d %b %Y, %I:%M %p"):
    """
    Format datetime in IST for orders
    """
    if datetime_obj is None:
        return "Date not available"
    
    if isinstance(datetime_obj, str):
        try:
            datetime_obj = parser.parse(datetime_obj)
        except:
            return datetime_obj
    
    try:
        if datetime_obj.tzinfo is None:
            datetime_obj = UTC_TIMEZONE.localize(datetime_obj)
        ist_time = datetime_obj.astimezone(IST_TIMEZONE)
        return ist_time.strftime(format_str)
    except Exception as e:
        print(f"⚠️ Format error: {e}")
        return str(datetime_obj)

# ✅ FLASK APP SETUP
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static',
    static_url_path='/static'
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# ✅ RAZORPAY CONFIGURATION
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_xxxxxxxxxxxx')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'your_test_secret_key')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', 'your_webhook_secret')

# Razorpay Client initialize
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

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

# ============================================
# ✅ SUPABASE HELPER FUNCTIONS
# ============================================

def get_supabase_client(use_admin=False):
    """Get Supabase client - use admin for write operations"""
    return supabase_admin if use_admin else supabase

def supabase_execute(table_name, operation='select', data=None, conditions=None, use_admin=True):
    """
    Execute Supabase operations consistently
    """
    client = get_supabase_client(use_admin)
    
    try:
        if operation == 'select':
            query = client.table(table_name).select('*')
            if conditions:
                for key, value in conditions.items():
                    if value is not None:
                        query = query.eq(key, value)
            result = query.execute()
            return result.data if hasattr(result, 'data') else []
            
        elif operation == 'insert':
            result = client.table(table_name).insert(data).execute()
            return result.data if hasattr(result, 'data') else []
            
        elif operation == 'update':
            query = client.table(table_name).update(data)
            if conditions:
                for key, value in conditions.items():
                    if value is not None:
                        query = query.eq(key, value)
            result = query.execute()
            return result.data if hasattr(result, 'data') else []
            
        elif operation == 'delete':
            query = client.table(table_name).delete()
            if conditions:
                for key, value in conditions.items():
                    if value is not None:
                        query = query.eq(key, value)
            result = query.execute()
            return result.data if hasattr(result, 'data') else []
            
        elif operation == 'upsert':
            result = client.table(table_name).upsert(data).execute()
            return result.data if hasattr(result, 'data') else []
            
    except Exception as e:
        print(f"❌ Supabase Error ({table_name}/{operation}): {e}")
        raise

def init_database():
    """Check Supabase connection"""
    print("🔗 Testing Supabase connection...")
    try:
        result = supabase.table('users').select('*').limit(1).execute()
        print("✅ Supabase connected successfully!")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        raise

# ✅ AUTOMATIC DATABASE INITIALIZATION
print("🚀 Starting Bite Me Buddy Application with Supabase...")
try:
    init_database()
    print("✅ Supabase connection successful!")
except Exception as e:
    print(f"⚠️ Supabase connection failed: {e}")

# ✅ LOGIN REQUIRED DECORATOR
def login_required(f):
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

@app.route('/health')
def health_check():
    try:
        result = supabase.table('users').select('*').limit(1).execute()
        return jsonify({
            'status': 'healthy',
            'service': 'Bite Me Buddy',
            'database': 'supabase',
            'connected': True,
            'timestamp': ist_now().isoformat(),
            'timezone': 'Asia/Kolkata'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'database': 'supabase',
            'connected': False,
            'timestamp': ist_now().isoformat(),
            'timezone': 'Asia/Kolkata'
        }), 500

@app.route('/init-db')
def init_db_route():
    try:
        init_database()
        return jsonify({
            'success': True,
            'message': 'Supabase connected successfully',
            'timestamp': ist_now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Supabase connection failed: {str(e)}',
            'timestamp': ist_now().isoformat()
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
            # Check if user exists
            existing_users = supabase_execute(
                'users',
                'select',
                conditions={'phone': phone},
                use_admin=True
            )
            
            if existing_users:
                flash('Phone number already registered', 'error')
                return render_template('register.html')
            
            existing_email = supabase_execute(
                'users',
                'select',
                conditions={'email': email},
                use_admin=True
            )
            
            if existing_email:
                flash('Email already registered', 'error')
                return render_template('register.html')
            
            # Insert new user
            user_data = {
                'profile_pic': profile_pic,
                'full_name': full_name,
                'phone': phone,
                'email': email,
                'location': location,
                'password': hashed_password,
                'is_active': True
            }
            
            new_user = supabase_execute('users', 'insert', data=user_data, use_admin=True)
            
            if new_user and len(new_user) > 0:
                user_id = new_user[0]['id']
                
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
                session['created_at'] = ist_now().strftime('%d %b %Y')
                
                flash('Registration successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Registration failed: No data returned', 'error')
                return render_template('register.html')
                    
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            print(f"❌ Registration error: {traceback.format_exc()}")
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
            # Get user by phone
            users = supabase_execute(
                'users',
                'select',
                conditions={'phone': phone}
            )
            
            if users and len(users) > 0:
                user = users[0]
                
                if check_password_hash(user['password'], password):
                    # Update last login
                    supabase_execute(
                        'users',
                        'update',
                        data={'last_login': 'now()'},
                        conditions={'id': user['id']},
                        use_admin=True
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
                    
                    # ✅ SUPER SIMPLE DATE FORMATTING - DIRECT IST
                    if user.get('created_at'):
                        try:
                            # Use simple formatter - no complex conversion
                            formatted_date = format_ist_date_simple(user['created_at'])
                            session['created_at'] = formatted_date
                            print(f"✅ Profile date set: {formatted_date}")
                        except Exception as e:
                            print(f"⚠️ Date error: {e}")
                            session['created_at'] = 'Recently'
                    else:
                        session['created_at'] = 'Recently'
                    
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid phone number or password', 'error')
                    return render_template('login.html')
            else:
                flash('Invalid phone number or password', 'error')
                return render_template('login.html')
                        
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'error')
            print(f"❌ Login error: {traceback.format_exc()}")
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
                print(f"⚠️ Admin fetch failed: {e}, using Supabase")
                services_list = supabase_execute(
                    'services',
                    'select',
                    conditions={'status': 'active'}
                )
                services_list = sorted(services_list, key=lambda x: (x.get('position', 0), x.get('name', '')))
        
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
                print(f"⚠️ Admin fetch failed: {e}, using Supabase")
                menu_items = supabase_execute(
                    'menu',
                    'select',
                    conditions={'status': 'active'}
                )
                menu_items = sorted(menu_items, key=lambda x: (x.get('position', 0), x.get('name', '')))
        
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
# ✅ CART ROUTES
# ============================================

@app.route('/cart')
@login_required
def cart():
    try:
        cart_items_db = supabase_execute(
            'cart',
            'select',
            conditions={'user_id': session['user_id']}
        )
        
        cart_items = []
        total_amount = 0
        
        for item in cart_items_db:
            if item['item_type'] == 'service':
                service = supabase_execute(
                    'services',
                    'select',
                    conditions={'id': item['item_id']}
                )
                if service:
                    service = service[0]
                    item_name = service['name']
                    item_price = float(service['final_price'])
                    item_description = service.get('description', '')
                    db_photo = service.get('photo', '')
            else:
                menu_item = supabase_execute(
                    'menu',
                    'select',
                    conditions={'id': item['item_id']}
                )
                if menu_item:
                    menu_item = menu_item[0]
                    item_name = menu_item['name']
                    item_price = float(menu_item['final_price'])
                    item_description = menu_item.get('description', '')
                    db_photo = menu_item.get('photo', '')
            
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
                'id': item['id'],
                'type': item['item_type'],
                'item_id': item['item_id'],
                'quantity': item['quantity'],
                'details': item_details,
                'item_total': item_total
            })
        
        return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)
    except Exception as e:
        print(f"❌ Cart error: {e}")
        flash(f'Error loading cart: {str(e)}', 'error')
        return render_template('cart.html', cart_items=[], total_amount=0)

def get_cloudinary_photo_for_cart(item_type, item_id, item_name):
    try:
        folder = SERVICES_FOLDER if item_type == 'service' else MENU_FOLDER
        
        if item_type == 'service':
            service = supabase_execute('services', 'select', conditions={'id': item_id})
            if service and service[0].get('photo') and service[0]['photo'].startswith('http'):
                return service[0]['photo']
        else:
            menu_item = supabase_execute('menu', 'select', conditions={'id': item_id})
            if menu_item and menu_item[0].get('photo') and menu_item[0]['photo'].startswith('http'):
                return menu_item[0]['photo']
        
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
        if item_type == 'service':
            item_exists = supabase_execute(
                'services',
                'select',
                conditions={'id': item_id, 'status': 'active'}
            )
        else:
            item_exists = supabase_execute(
                'menu',
                'select',
                conditions={'id': item_id, 'status': 'active'}
            )
        
        if not item_exists:
            return jsonify({'success': False, 'message': 'Item not available'})
        
        existing = supabase_execute(
            'cart',
            'select',
            conditions={
                'user_id': session['user_id'],
                'item_type': item_type,
                'item_id': item_id
            }
        )
        
        if existing:
            new_quantity = existing[0]['quantity'] + quantity
            supabase_execute(
                'cart',
                'update',
                data={'quantity': new_quantity},
                conditions={'id': existing[0]['id']},
                use_admin=True
            )
        else:
            cart_data = {
                'user_id': session['user_id'],
                'item_type': item_type,
                'item_id': item_id,
                'quantity': quantity
            }
            supabase_execute('cart', 'insert', data=cart_data, use_admin=True)
        
        return jsonify({'success': True, 'message': 'Item added to cart'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/update_cart', methods=['POST'])
@login_required
def update_cart():
    cart_id = request.form.get('cart_id')
    action = request.form.get('action')
    
    try:
        cart_item = supabase_execute(
            'cart',
            'select',
            conditions={'id': cart_id, 'user_id': session['user_id']}
        )
        
        if not cart_item:
            return jsonify({'success': False, 'message': 'Item not found'})
        
        item = cart_item[0]
        new_quantity = item['quantity']
        
        if action == 'increase':
            new_quantity += 1
        elif action == 'decrease':
            new_quantity -= 1
        
        if new_quantity <= 0:
            supabase_execute(
                'cart',
                'delete',
                conditions={'id': cart_id},
                use_admin=True
            )
        else:
            supabase_execute(
                'cart',
                'update',
                data={'quantity': new_quantity},
                conditions={'id': cart_id},
                use_admin=True
            )
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/remove_from_cart/<int:cart_id>', methods=['POST'])
@login_required
def remove_from_cart(cart_id):
    try:
        supabase_execute(
            'cart',
            'delete',
            conditions={'id': cart_id, 'user_id': session['user_id']},
            use_admin=True
        )
        
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
        print(f"🔍 [CHECKOUT] Payment mode: {payment_mode}")
        
        if not payment_mode or not delivery_location:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Payment mode and delivery location are required'})
            flash('Payment mode and delivery location are required', 'error')
            return redirect(url_for('cart'))
        
        try:
            cart_items = supabase_execute(
                'cart',
                'select',
                conditions={'user_id': session['user_id']}
            )
            
            if not cart_items:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Your cart is empty'})
                flash('Your cart is empty', 'error')
                return redirect(url_for('cart'))
            
            total_amount = 0
            items_list = []
            
            for item in cart_items:
                if item['item_type'] == 'service':
                    details = supabase_execute(
                        'services',
                        'select',
                        conditions={'id': item['item_id']}
                    )
                else:
                    details = supabase_execute(
                        'menu',
                        'select',
                        conditions={'id': item['item_id']}
                    )
                
                if details:
                    details = details[0]
                    item_price = float(details['final_price'])
                    item_total = item_price * item['quantity']
                    total_amount += item_total
                    
                    items_list.append({
                        'item_type': item['item_type'],
                        'item_id': item['item_id'],
                        'item_name': details['name'],
                        'item_photo': details.get('photo', ''),
                        'item_description': details.get('description', ''),
                        'quantity': item['quantity'],
                        'price': item_price,
                        'total': item_total
                    })
            
            items_json = json.dumps(items_list)
            
            if payment_mode == 'online':
                order_data = {
                    'user_id': session['user_id'],
                    'user_name': session.get('full_name', ''),
                    'user_email': session.get('email', ''),
                    'user_phone': session.get('phone', ''),
                    'user_address': session.get('location', ''),
                    'items': items_json,
                    'total_amount': total_amount,
                    'payment_mode': payment_mode,
                    'delivery_location': delivery_location,
                    'status': 'pending_payment'
                }
                
                new_order = supabase_execute('orders', 'insert', data=order_data, use_admin=True)
                
                if not new_order:
                    raise Exception("Failed to create order")
                
                order_id = new_order[0]['order_id']
                
                payment_data = {
                    'order_id': order_id,
                    'user_id': session['user_id'],
                    'amount': total_amount,
                    'payment_mode': payment_mode,
                    'payment_status': 'pending'
                }
                
                supabase_execute('payments', 'insert', data=payment_data, use_admin=True)
                
                supabase_execute(
                    'cart',
                    'delete',
                    conditions={'user_id': session['user_id']},
                    use_admin=True
                )
                
                print(f"✅ [CHECKOUT] Online order #{order_id} created")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True, 
                        'order_id': order_id,
                        'redirect_url': url_for('payment_page', order_id=order_id)
                    })
                
                return redirect(url_for('payment_page', order_id=order_id))
            
            else:
                order_data = {
                    'user_id': session['user_id'],
                    'user_name': session.get('full_name', ''),
                    'user_email': session.get('email', ''),
                    'user_phone': session.get('phone', ''),
                    'user_address': session.get('location', ''),
                    'items': items_json,
                    'total_amount': total_amount,
                    'payment_mode': payment_mode,
                    'delivery_location': delivery_location,
                    'status': 'pending'
                }
                
                new_order = supabase_execute('orders', 'insert', data=order_data, use_admin=True)
                
                if not new_order:
                    raise Exception("Failed to create order")
                
                order_id = new_order[0]['order_id']
                
                payment_data = {
                    'order_id': order_id,
                    'user_id': session['user_id'],
                    'amount': total_amount,
                    'payment_mode': payment_mode,
                    'payment_status': 'pending'
                }
                
                supabase_execute('payments', 'insert', data=payment_data, use_admin=True)
                
                supabase_execute(
                    'cart',
                    'delete',
                    conditions={'user_id': session['user_id']},
                    use_admin=True
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'order_id': order_id,
                        'redirect_url': url_for('order_history')
                    })
                
                flash('Order placed successfully! Pay when delivered.', 'success')
                return redirect(url_for('order_history'))
                    
        except Exception as e:
            print(f"❌ [CHECKOUT ERROR] {str(e)}")
            traceback.print_exc()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': f'Error placing order: {str(e)}'})
            
            flash(f'Error placing order: {str(e)}', 'error')
            return redirect(url_for('cart'))
    
    # GET REQUEST
    try:
        cart_items = supabase_execute(
            'cart',
            'select',
            conditions={'user_id': session['user_id']}
        )
        
        cart_items_list = []
        cart_total = 0
        
        for item in cart_items:
            if item['item_type'] == 'service':
                details = supabase_execute(
                    'services',
                    'select',
                    conditions={'id': item['item_id']}
                )
            else:
                details = supabase_execute(
                    'menu',
                    'select',
                    conditions={'id': item['item_id']}
                )
            
            if details:
                details = details[0]
                item_details = {
                    'name': details['name'],
                    'photo': details.get('photo', ''),
                    'description': details.get('description', ''),
                    'price': float(details['final_price'])
                }
                
                item_total = item_details['price'] * item['quantity']
                cart_total += item_total
                
                cart_items_list.append({
                    'id': item['id'],
                    'type': item['item_type'],
                    'item_id': item['item_id'],
                    'quantity': item['quantity'],
                    'details': item_details,
                    'item_total': item_total
                })
        
    except Exception as e:
        cart_items = []
        cart_total = 0
        print(f"⚠️ [CHECKOUT GET ERROR] {e}")
    
    return render_template('checkout.html', 
                         cart_items=cart_items_list, 
                         cart_total=cart_total,
                         razorpay_key_id=RAZORPAY_KEY_ID)

# ============================================
# ✅ RAZORPAY PAYMENT ROUTES
# ============================================

@app.route('/payment/<int:order_id>')
@login_required
def payment_page(order_id):
    try:
        orders = supabase_execute(
            'orders',
            'select',
            conditions={'order_id': order_id, 'user_id': session['user_id']}
        )
        
        payments = supabase_execute(
            'payments',
            'select',
            conditions={'order_id': order_id, 'user_id': session['user_id']}
        )
        
        if not orders:
            flash('Order not found', 'error')
            return redirect(url_for('order_history'))
        
        order = orders[0]
        payment = payments[0] if payments else {'payment_status': 'pending'}
        
        if order['payment_mode'] != 'online':
            flash('This order is not for online payment', 'error')
            return redirect(url_for('order_history'))
        
        if payment['payment_status'] == 'paid':
            flash('Payment already completed', 'info')
            return redirect(url_for('order_details', order_id=order_id))
        
        return render_template('payment.html',
                             order_id=order_id,
                             amount=order['total_amount'],
                             razorpay_key_id=RAZORPAY_KEY_ID)
            
    except Exception as e:
        print(f"❌ [PAYMENT PAGE ERROR] {str(e)}")
        flash(f'Error loading payment page: {str(e)}', 'error')
        return redirect(url_for('order_history'))

@app.route('/create_razorpay_order', methods=['POST'])
@login_required
def create_razorpay_order():
    try:
        data = request.json
        amount = float(data.get('amount', 0))
        order_id = data.get('order_id')
        
        print(f"🔍 [RAZORPAY] Creating order for amount: ₹{amount}, Order ID: {order_id}")
        
        if amount <= 0:
            return jsonify({'success': False, 'message': 'Invalid amount'})
        
        amount_in_paise = int(amount * 100)
        
        order_data = {
            'amount': amount_in_paise,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'order_id': order_id,
                'user_id': session['user_id'],
                'user_name': session.get('full_name', '')
            }
        }
        
        razorpay_order = razorpay_client.order.create(data=order_data)
        
        print(f"✅ [RAZORPAY] Order created: {razorpay_order['id']}")
        
        return jsonify({
            'success': True,
            'order_id': razorpay_order['id'],
            'amount': razorpay_order['amount'],
            'currency': razorpay_order['currency'],
            'razorpay_key_id': RAZORPAY_KEY_ID
        })
        
    except Exception as e:
        print(f"❌ [RAZORPAY ERROR] {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/verify_razorpay_payment', methods=['POST'])
@login_required
def verify_razorpay_payment():
    try:
        data = request.json
        
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')
        order_id = data.get('order_id')
        
        print(f"🔍 [RAZORPAY VERIFY] Verifying payment: {razorpay_payment_id}")
        
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        payment = razorpay_client.payment.fetch(razorpay_payment_id)
        
        print(f"✅ [RAZORPAY] Payment verified: {payment['id']}, Status: {payment['status']}")
        
        supabase_execute(
            'orders',
            'update',
            data={'status': 'confirmed'},
            conditions={'order_id': order_id, 'user_id': session['user_id']},
            use_admin=True
        )
        
        supabase_execute(
            'payments',
            'update',
            data={
                'payment_status': 'paid',
                'transaction_id': razorpay_payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature,
                'payment_date': 'now()'
            },
            conditions={'order_id': order_id, 'user_id': session['user_id']},
            use_admin=True
        )
        
        print(f"✅ [RAZORPAY] Supabase updated for order #{order_id}")
        
        return jsonify({
            'success': True,
            'payment_id': razorpay_payment_id,
            'status': payment['status'],
            'amount': payment['amount'] / 100,
            'method': payment.get('method', 'online')
        })
        
    except razorpay.errors.SignatureVerificationError:
        print(f"❌ [RAZORPAY] Signature verification failed")
        return jsonify({'success': False, 'message': 'Invalid payment signature'}), 400
        
    except Exception as e:
        print(f"❌ [RAZORPAY VERIFY ERROR] {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/payment_success')
@login_required
def payment_success():
    payment_id = request.args.get('payment_id')
    order_id = request.args.get('order_id')
    
    try:
        payment = razorpay_client.payment.fetch(payment_id)
        
        return render_template('payment_success.html',
                             payment_id=payment_id,
                             order_id=order_id,
                             amount=payment['amount'] / 100,
                             method=payment.get('method', 'online').upper(),
                             status=payment['status'])
        
    except Exception as e:
        print(f"⚠️ Error loading payment details: {e}")
        return render_template('payment_success.html',
                             payment_id=payment_id,
                             order_id=order_id,
                             amount=0,
                             method='ONLINE',
                             status='success')

@app.route('/payment_failed')
@login_required
def payment_failed():
    order_id = request.args.get('order_id')
    reason = request.args.get('reason', 'Payment failed or was cancelled')
    
    return render_template('payment_failed.html',
                         order_id=order_id,
                         reason=reason)

@app.route('/razorpay_webhook', methods=['POST'])
def razorpay_webhook():
    try:
        webhook_signature = request.headers.get('X-Razorpay-Signature', '')
        webhook_body = request.get_data(as_text=True)
        
        print(f"🔍 [WEBHOOK] Received webhook")
        
        expected_signature = hmac.new(
            key=RAZORPAY_WEBHOOK_SECRET.encode(),
            msg=webhook_body.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(webhook_signature, expected_signature):
            print(f"❌ [WEBHOOK] Invalid signature")
            return jsonify({'error': 'Invalid signature'}), 400
        
        data = request.json
        event = data.get('event')
        
        print(f"✅ [WEBHOOK] Event: {event}")
        
        if event == 'payment.captured':
            payment = data['payload']['payment']['entity']
            notes = payment.get('notes', {})
            order_id = notes.get('order_id')
            user_id = notes.get('user_id')
            
            if order_id and user_id:
                supabase_execute(
                    'orders',
                    'update',
                    data={'status': 'confirmed'},
                    conditions={'order_id': order_id, 'user_id': user_id},
                    use_admin=True
                )
                
                supabase_execute(
                    'payments',
                    'update',
                    data={
                        'payment_status': 'paid',
                        'transaction_id': payment['id'],
                        'razorpay_order_id': payment['order_id'],
                        'razorpay_payment_id': payment['id'],
                        'payment_date': 'now()'
                    },
                    conditions={'order_id': order_id, 'user_id': user_id},
                    use_admin=True
                )
                
                print(f"✅ [WEBHOOK] Updated order #{order_id}")
        
        elif event == 'payment.failed':
            payment = data['payload']['payment']['entity']
            notes = payment.get('notes', {})
            order_id = notes.get('order_id')
            user_id = notes.get('user_id')
            
            if order_id and user_id:
                supabase_execute(
                    'payments',
                    'update',
                    data={
                        'payment_status': 'failed',
                        'transaction_id': payment['id']
                    },
                    conditions={'order_id': order_id, 'user_id': user_id},
                    use_admin=True
                )
                
                print(f"⚠️ [WEBHOOK] Payment failed for order #{order_id}")
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        print(f"❌ [WEBHOOK ERROR] {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/check_payment_status/<int:order_id>')
@login_required
def check_payment_status(order_id):
    try:
        payments = supabase_execute(
            'payments',
            'select',
            conditions={'order_id': order_id, 'user_id': session['user_id']}
        )
        
        orders = supabase_execute(
            'orders',
            'select',
            conditions={'order_id': order_id, 'user_id': session['user_id']}
        )
        
        if payments and orders:
            payment = payments[0]
            order = orders[0]
            
            return jsonify({
                'success': True,
                'payment_status': payment['payment_status'],
                'order_status': order['status'],
                'transaction_id': payment.get('transaction_id'),
                'payment_date': format_ist_datetime(payment.get('payment_date')) if payment.get('payment_date') else None
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Payment not found'
            })
                
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# ✅ ORDER HISTORY ROUTE
# ============================================

@app.route('/order_history')
@login_required
def order_history():
    try:
        orders_data = supabase_execute(
            'orders',
            'select',
            conditions={'user_id': session['user_id']}
        )
        
        orders_data = sorted(orders_data, key=lambda x: x.get('order_date', ''), reverse=True)
        
        orders_list = []
        total_orders = len(orders_data)
        
        for index, order in enumerate(orders_data):
            customer_order_no = total_orders - index
            
            if order.get('order_date'):
                try:
                    order['order_date_formatted'] = format_ist_datetime(
                        order['order_date'],
                        "%d %b %Y, %I:%M %p"
                    )
                except Exception as e:
                    print(f"⚠️ Date error: {e}")
                    order['order_date_formatted'] = str(order['order_date'])
            else:
                order['order_date_formatted'] = 'Date not available'
            
            if order.get('delivery_date'):
                try:
                    order['delivery_date_formatted'] = format_ist_datetime(
                        order['delivery_date'],
                        "%d %b %Y, %I:%M %p"
                    )
                except Exception as e:
                    print(f"⚠️ Delivery date error: {e}")
                    order['delivery_date_formatted'] = str(order['delivery_date'])
            
            items_list = []
            if order.get('items'):
                try:
                    json_items = json.loads(order['items'])
                    if isinstance(json_items, list):
                        for item in json_items:
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
                    print(f"❌ JSON error: {e}")
                    items_list = []
            
            payment_status = 'pending'
            try:
                payments = supabase_execute(
                    'payments',
                    'select',
                    conditions={'order_id': order['order_id']}
                )
                if payments:
                    payment_status = payments[0].get('payment_status', 'pending')
            except Exception:
                payment_status = order.get('payment_mode', 'COD')
            
            orders_list.append({
                'order_id': order['order_id'],
                'order_no': customer_order_no,
                'user_name': order.get('user_name', session.get('full_name', '')),
                'user_email': order.get('user_email', session.get('email', '')),
                'user_phone': order.get('user_phone', session.get('phone', '')),
                'user_address': order.get('user_address', session.get('location', '')),
                'total_amount': float(order.get('total_amount', 0)),
                'payment_mode': order.get('payment_mode', 'COD'),
                'payment_status': payment_status,
                'delivery_location': order.get('delivery_location', 'Location not specified'),
                'status': order.get('status', 'pending'),
                'order_date': order.get('order_date'),
                'order_date_formatted': order.get('order_date_formatted', 'Date not available'),
                'delivery_date_formatted': order.get('delivery_date_formatted'),
                'items': items_list
            })
        
        return render_template('orders.html', orders=orders_list or [])
        
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
    try:
        orders = supabase_execute(
            'orders',
            'select',
            conditions={'order_id': order_id, 'user_id': session['user_id']}
        )
        
        if not orders:
            flash('Order not found', 'error')
            return redirect(url_for('order_history'))
        
        order = orders[0]
        
        all_user_orders = supabase_execute(
            'orders',
            'select',
            conditions={'user_id': session['user_id']}
        )
        all_user_orders = sorted(all_user_orders, key=lambda x: x.get('order_date', ''), reverse=True)
        
        customer_order_no = None
        for index, user_order in enumerate(all_user_orders):
            if user_order['order_id'] == order_id:
                customer_order_no = len(all_user_orders) - index
                break
        
        if customer_order_no is None:
            customer_order_no = 1
        
        if order.get('order_date'):
            try:
                order['order_date_formatted'] = format_ist_datetime(
                    order['order_date'], 
                    "%d %b %Y, %I:%M %p"
                )
            except Exception as e:
                print(f"⚠️ Date error: {e}")
                order['order_date_formatted'] = str(order['order_date'])
        else:
            order['order_date_formatted'] = 'Date not available'
        
        if order.get('delivery_date'):
            try:
                order['delivery_date_formatted'] = format_ist_datetime(
                    order['delivery_date'],
                    "%d %b %Y, %I:%M %p"
                )
            except Exception as e:
                print(f"⚠️ Delivery date error: {e}")
                order['delivery_date_formatted'] = str(order['delivery_date'])
        
        payment_status = 'pending'
        try:
            payments = supabase_execute(
                'payments',
                'select',
                conditions={'order_id': order_id}
            )
            if payments:
                payment = payments[0]
                order['payment_status'] = payment.get('payment_status', 'pending')
                order['transaction_id'] = payment.get('transaction_id')
                order['payment_date'] = payment.get('payment_date')
                
                if order.get('payment_date'):
                    try:
                        order['payment_date_formatted'] = format_ist_datetime(
                            order['payment_date'],
                            "%d %b %Y, %I:%M %p"
                        )
                    except Exception as e:
                        print(f"⚠️ Payment date error: {e}")
                        order['payment_date_formatted'] = str(order['payment_date'])
        except Exception as e:
            print(f"⚠️ Payment details error: {e}")
            order['payment_status'] = order.get('payment_mode', 'pending')
        
        items_list = []
        if order.get('items'):
            try:
                json_items = json.loads(order['items'])
                if isinstance(json_items, list):
                    for item in json_items:
                        items_list.append({
                            'name': item.get('item_name', item.get('name', 'Unknown Item')),
                            'item_name': item.get('item_name', item.get('name', 'Unknown Item')),
                            'type': item.get('item_type', item.get('type', 'unknown')),
                            'item_type': item.get('item_type', item.get('type', 'unknown')),
                            'item_id': item.get('item_id', 0),
                            'photo': item.get('item_photo', item.get('photo', '')),
                            'description': item.get('item_description', item.get('description', '')),
                            'quantity': int(item.get('quantity', 1)),
                            'price': float(item.get('price', 0)),
                            'total': float(item.get('total', 0))
                        })
            except Exception as e:
                print(f"JSON parse error: {e}")
                items_list = []
        
        order['order_no'] = customer_order_no
        
        return render_template('order_details.html', 
                             order=order, 
                             items=items_list)
                
    except Exception as e:
        print(f"❌ [ORDER_DETAILS ERROR] {str(e)}")
        traceback.print_exc()
        flash(f'Error loading order details: {str(e)}', 'error')
        return redirect(url_for('order_history'))

# ============================================
# ✅ DEBUG USER ORDERS ROUTE
# ============================================

@app.route('/debug-user-orders')
@login_required
def debug_user_orders():
    try:
        all_orders = supabase_execute('orders', 'select')
        total_orders = len(all_orders) if all_orders else 0
        
        user_orders = supabase_execute(
            'orders',
            'select',
            conditions={'user_id': session['user_id']}
        )
        user_orders = sorted(user_orders, key=lambda x: x.get('order_date', ''), reverse=True) if user_orders else []
        
        all_users = supabase_execute('users', 'select')
        users_with_counts = []
        
        for user in all_users or []:
            user_orders_count = supabase_execute(
                'orders',
                'select',
                conditions={'user_id': user['id']}
            )
            count = len(user_orders_count) if user_orders_count else 0
            users_with_counts.append({
                'user_id': user['id'],
                'full_name': user.get('full_name', ''),
                'phone': user.get('phone', ''),
                'order_count': count
            })
        
        users_with_counts = sorted(users_with_counts, key=lambda x: x['order_count'], reverse=True)
        
        html = f"""
        <html>
        <head>
            <title>Orders Debug Information - Supabase</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .user-info {{ background-color: #e6f7ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .stats {{ background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h2>Orders Debug Information - Supabase</h2>
            
            <div class="user-info">
                <h3>Current User Info:</h3>
                <p><strong>User ID:</strong> {session['user_id']}</p>
                <p><strong>User Name:</strong> {session.get('full_name', 'N/A')}</p>
                <p><strong>User Phone:</strong> {session.get('phone', 'N/A')}</p>
                <p><strong>User's Total Orders:</strong> {len(user_orders)}</p>
            </div>
            
            <div class="stats">
                <h3>Database Stats:</h3>
                <p><strong>Total Orders in Database:</strong> {total_orders}</p>
                <p><strong>Total Users:</strong> {len(all_users or [])}</p>
            </div>
            
            <h3>Current User's Orders:</h3>
            <table border="1">
                <tr>
                    <th>#</th>
                    <th>Order ID</th>
                    <th>User ID</th>
                    <th>User Name</th>
                    <th>Order Date (UTC)</th>
                    <th>Order Date (IST)</th>
                    <th>Customer Order #</th>
                </tr>
        """
        
        for index, order in enumerate(user_orders):
            customer_order_no = len(user_orders) - index
            utc_date = order.get('order_date', 'N/A')
            ist_date = format_ist_datetime(order.get('order_date'), "%d %b %Y, %I:%M %p")
            html += f"""
                <tr>
                    <td>{index + 1}</td>
                    <td>{order['order_id']}</td>
                    <td>{order['user_id']}</td>
                    <td>{order.get('user_name', 'N/A')}</td>
                    <td>{utc_date}</td>
                    <td><strong>{ist_date}</strong></td>
                    <td><strong>{customer_order_no}</strong></td>
                </tr>
            """
        
        html += f"""
            </table>
            
            <h3>All Users Order Count:</h3>
            <table border="1">
                <tr>
                    <th>User ID</th>
                    <th>Name</th>
                    <th>Phone</th>
                    <th>Total Orders</th>
                </tr>
        """
        
        for user in users_with_counts:
            html += f"""
                <tr>
                    <td>{user['user_id']}</td>
                    <td>{user['full_name']}</td>
                    <td>{user['phone']}</td>
                    <td>{user['order_count']}</td>
                </tr>
            """
        
        html += f"""
            </table>
            
            <hr>
            <p><a href="/order_history">← Back to Order History</a></p>
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        return f"<h2>Error</h2><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>"

# ============================================
# ✅ DEBUG DATE ROUTE
# ============================================

@app.route('/debug-date')
@login_required
def debug_date():
    """Debug date issue"""
    try:
        users = supabase_execute(
            'users',
            'select',
            conditions={'id': session['user_id']}
        )
        
        user = users[0] if users else {}
        db_date = user.get('created_at')
        
        formatted_dates = []
        
        if db_date:
            formatted_dates.append(f"Raw from DB: {db_date}")
            formatted_dates.append(f"Type: {type(db_date)}")
            
            try:
                formatted = format_ist_date_simple(db_date)
                formatted_dates.append(f"Formatted with simple function: <strong>{formatted}</strong>")
            except Exception as e:
                formatted_dates.append(f"Simple function error: {e}")
        
        return f"""
        <html>
        <head>
            <title>Date Debug</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .info {{ background-color: #e6f7ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h2>📅 Date Debug Information</h2>
            
            <div class="info">
                <h3>Current User:</h3>
                <p><strong>User ID:</strong> {session['user_id']}</p>
                <p><strong>User Name:</strong> {session.get('full_name', 'N/A')}</p>
                <p><strong>Session created_at:</strong> {session.get('created_at', 'N/A')}</p>
            </div>
            
            <h3>Database created_at:</h3>
            <pre>{chr(10).join(formatted_dates)}</pre>
            
            <hr>
            <p><a href="/profile">🔙 Back to Profile</a></p>
            <p><a href="/order_history">📦 Back to Orders</a></p>
        </body>
        </html>
        """
    except Exception as e:
        return f"<h2>Error</h2><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>"

# ============================================
# ✅ CANCEL ORDER ROUTE
# ============================================

@app.route('/cancel-order/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    try:
        orders = supabase_execute(
            'orders',
            'select',
            conditions={'order_id': order_id, 'user_id': session['user_id']}
        )
        
        if not orders:
            return jsonify({'success': False, 'message': 'Order not found'})
        
        order = orders[0]
        
        if order['status'] != 'pending':
            return jsonify({
                'success': False, 
                'message': f'Order cannot be cancelled. Current status: {order["status"]}'
            })
        
        supabase_execute(
            'orders',
            'update',
            data={'status': 'cancelled'},
            conditions={'order_id': order_id, 'user_id': session['user_id']},
            use_admin=True
        )
        
        try:
            supabase_execute(
                'payments',
                'update',
                data={'payment_status': 'refunded'},
                conditions={'order_id': order_id},
                use_admin=True
            )
        except Exception as e:
            print(f"⚠️ Payment update failed: {e}")
        
        print(f"✅ [CANCEL_ORDER] Order #{order_id} cancelled by user {session['user_id']}")
        
        return jsonify({
            'success': True, 
            'message': 'Order cancelled successfully'
        })
                
    except Exception as e:
        print(f"❌ [CANCEL_ORDER ERROR] {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# ✅ PROFILE ROUTE
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
            existing_email = supabase_execute(
                'users',
                'select',
                conditions={'email': email}
            )
            
            if existing_email and existing_email[0]['id'] != session['user_id']:
                flash('Email already registered to another account', 'error')
                return render_template('profile.html')
            
            update_data = {
                'full_name': full_name,
                'email': email,
                'location': location,
                'profile_pic': profile_pic
            }
            
            if new_password:
                update_data['password'] = generate_password_hash(new_password)
            
            supabase_execute(
                'users',
                'update',
                data=update_data,
                conditions={'id': session['user_id']},
                use_admin=True
            )
            
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
    try:
        addresses_list = supabase_execute(
            'addresses',
            'select',
            conditions={'user_id': session['user_id']}
        )
        
        addresses_list = sorted(addresses_list,
                              key=lambda x: (not x.get('is_default', False), x.get('created_at', '')),
                              reverse=False)
        
        return render_template('addresses.html', addresses=addresses_list)
    except Exception as e:
        flash(f'Error loading addresses: {str(e)}', 'error')
        return render_template('addresses.html', addresses=[])

@app.route('/add_address', methods=['POST'])
@login_required
def add_address():
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
        
        if is_default:
            supabase_execute(
                'addresses',
                'update',
                data={'is_default': False},
                conditions={'user_id': session['user_id']},
                use_admin=True
            )
        
        address_data = {
            'user_id': session['user_id'],
            'full_name': full_name,
            'phone': phone,
            'address_line1': address_line1,
            'address_line2': address_line2,
            'landmark': landmark,
            'city': city,
            'state': state,
            'pincode': pincode,
            'is_default': is_default
        }
        
        supabase_execute('addresses', 'insert', data=address_data, use_admin=True)
        
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
    try:
        notifications_list = supabase_execute(
            'notifications',
            'select',
            conditions={'user_id': session['user_id']}
        )
        
        notifications_list = sorted(notifications_list,
                                  key=lambda x: x.get('created_at', ''),
                                  reverse=True)
        
        supabase_execute(
            'notifications',
            'update',
            data={'is_read': True, 'read_at': 'now()'},
            conditions={'user_id': session['user_id'], 'is_read': False},
            use_admin=True
        )
        
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
    try:
        user_orders = supabase_execute(
            'orders',
            'select',
            conditions={'user_id': session['user_id']}
        )
        
        order_dates = [o.get('order_date') for o in user_orders] if user_orders else []
        
        sample_orders = []
        if user_orders:
            user_orders_sorted = sorted(user_orders, key=lambda x: x.get('order_date', ''), reverse=True)
            for order in user_orders_sorted[:5]:
                items_length = len(order.get('items', '')) if order.get('items') else 0
                items_preview = order.get('items', '')[:100] if order.get('items') else ''
                
                sample_orders.append({
                    'order_id': order['order_id'],
                    'total_amount': order.get('total_amount'),
                    'status': order.get('status'),
                    'order_date': str(order.get('order_date')) if order.get('order_date') else None,
                    'items_length': items_length,
                    'items_preview': items_preview
                })
        
        return jsonify({
            'success': True,
            'user_id': session['user_id'],
            'user_name': session.get('full_name', 'Unknown'),
            'orders_stats': {
                'total_orders': len(user_orders) if user_orders else 0,
                'latest_order': str(max(order_dates)) if order_dates else 'None',
                'first_order': str(min(order_dates)) if order_dates else 'None'
            },
            'sample_orders': sample_orders
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/fix-all-orders')
@login_required
def fix_all_orders():
    try:
        orders = supabase_execute(
            'orders',
            'select',
            conditions={'user_id': session['user_id']}
        )
        
        if not orders:
            return "<h2>No orders found for this user</h2>"
        
        orders = sorted(orders, key=lambda x: x.get('order_date', ''))
        
        results = []
        total_fixed = 0
        
        for order in orders:
            order_id = order['order_id']
            items_json = order.get('items')
            
            if items_json:
                try:
                    items_list = json.loads(items_json)
                    new_items = []
                    
                    for item in items_list:
                        if item.get('item_type') == 'service':
                            details = supabase_execute(
                                'services',
                                'select',
                                conditions={'id': item.get('item_id')}
                            )
                        else:
                            details = supabase_execute(
                                'menu',
                                'select',
                                conditions={'id': item.get('item_id')}
                            )
                        
                        if details:
                            details = details[0]
                            item['item_name'] = details.get('name', item.get('item_name', ''))
                            item['item_photo'] = details.get('photo', item.get('item_photo', ''))
                            item['item_description'] = details.get('description', item.get('item_description', ''))
                        
                        new_items.append(item)
                    
                    new_json = json.dumps(new_items)
                    supabase_execute(
                        'orders',
                        'update',
                        data={'items': new_json},
                        conditions={'order_id': order_id},
                        use_admin=True
                    )
                    
                    total_fixed += 1
                    results.append(f"✅ Order #{order_id}: Fixed")
                    
                except Exception as e:
                    results.append(f"❌ Order #{order_id}: ERROR - {str(e)}")
            else:
                results.append(f"⚠️ Order #{order_id}: No items JSON")
        
        return f"""
        <h2>Order Fix Results - Supabase</h2>
        <p>User: {session.get('full_name')} (ID: {session['user_id']})</p>
        <p>Total Orders: {len(orders)}</p>
        <p>Fixed: {total_fixed}</p>
        <hr>
        {'<br>'.join(results)}
        <hr>
        <p><a href="/order_history">← Back to Order History</a></p>
        """
        
    except Exception as e:
        return f"<h2>Error</h2><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>"

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
            
            supabase_execute(
                'users',
                'update',
                data={'profile_pic': uploaded_url},
                conditions={'id': session['user_id']},
                use_admin=True
            )
            
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
        services = supabase_execute(
            'services',
            'select',
            conditions={'id': service_id, 'status': 'active'}
        )
        
        if services:
            service = services[0]
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
        menu_items = supabase_execute(
            'menu',
            'select',
            conditions={'id': menu_id, 'status': 'active'}
        )
        
        if menu_items:
            menu_item = menu_items[0]
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
            users = supabase_execute(
                'users',
                'select',
                conditions={'phone': mobile}
            )
            
            if not users:
                flash('Mobile number not registered', 'error')
                return redirect('/forgot-password')
            
            supabase_execute(
                'users',
                'update',
                data={'password': hashed_password},
                conditions={'phone': mobile},
                use_admin=True
            )
            
            flash('Password reset successful! Please login with new password.', 'success')
            return redirect(url_for('login'))
            
        except Exception as db_error:
            flash(f'Database error: {str(db_error)}', 'error')
            return redirect('/forgot-password')
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect('/forgot-password')

# ============================================
# ✅ TEST ROUTES FOR DEBUGGING
# ============================================

@app.route('/test-fetchall')
def test_fetchall():
    try:
        result = supabase_execute('users', 'select', conditions={}, use_admin=True)
        return jsonify({
            'type': str(type(result)),
            'is_list': isinstance(result, list),
            'length': len(result) if result else 0,
            'data': result[:1] if result else []
        })
    except Exception as e:
        return jsonify({'error': str(e)})

# ============================================
# ✅ ORDER MANAGEMENT ROUTES
# ============================================

@app.route('/track-order/<int:order_id>')
@login_required
def track_order(order_id):
    try:
        orders = supabase_execute(
            'orders',
            'select',
            conditions={'order_id': order_id, 'user_id': session['user_id']}
        )
        
        if not orders:
            flash('Order not found', 'error')
            return redirect(url_for('order_history'))
        
        order = orders[0]
        
        payments = supabase_execute(
            'payments',
            'select',
            conditions={'order_id': order_id}
        )
        
        if payments:
            order['payment_status'] = payments[0].get('payment_status', 'pending')
        
        delivery_details = {
            'name': 'Delivery Partner',
            'phone': '+91 9876543210',
            'estimated_time': '30-45 minutes',
            'status': 'on_the_way' if order['status'] == 'processing' else 'pending'
        }
        
        return render_template('track_order.html', 
                             order=order, 
                             delivery_details=delivery_details)
                
    except Exception as e:
        flash(f'Error tracking order: {str(e)}', 'error')
        return redirect(url_for('order_history'))

@app.route('/reorder/<int:order_id>', methods=['POST'])
@login_required
def reorder(order_id):
    try:
        order_items = supabase_execute(
            'order_items',
            'select',
            conditions={'order_id': order_id}
        )
        
        if not order_items:
            orders = supabase_execute(
                'orders',
                'select',
                conditions={'order_id': order_id, 'user_id': session['user_id']}
            )
            
            if orders and orders[0].get('items'):
                items_json = json.loads(orders[0]['items'])
                order_items = []
                for item in items_json:
                    order_items.append({
                        'item_type': item['item_type'],
                        'item_id': item['item_id'],
                        'quantity': item['quantity']
                    })
        
        if not order_items:
            flash('No items found in this order', 'error')
            return redirect(url_for('order_history'))
        
        added_count = 0
        for item in order_items:
            try:
                existing = supabase_execute(
                    'cart',
                    'select',
                    conditions={
                        'user_id': session['user_id'],
                        'item_type': item['item_type'],
                        'item_id': item['item_id']
                    }
                )
                
                if existing:
                    new_quantity = existing[0]['quantity'] + item['quantity']
                    supabase_execute(
                        'cart',
                        'update',
                        data={'quantity': new_quantity},
                        conditions={'id': existing[0]['id']},
                        use_admin=True
                    )
                else:
                    cart_data = {
                        'user_id': session['user_id'],
                        'item_type': item['item_type'],
                        'item_id': item['item_id'],
                        'quantity': item['quantity']
                    }
                    supabase_execute('cart', 'insert', data=cart_data, use_admin=True)
                
                added_count += 1
                
            except Exception as e:
                print(f"Error adding item {item.get('item_id')}: {e}")
        
        flash(f'{added_count} items added to cart from order #{order_id}', 'success')
        return redirect(url_for('cart'))
        
    except Exception as e:
        flash(f'Error reordering: {str(e)}', 'error')
        return redirect(url_for('order_history'))

# ============================================
# ✅ CONTEXT PROCESSOR
# ============================================

@app.context_processor
def utility_processor():
    def get_user_friendly_location(location_string):
        parsed = parse_location_data(location_string)
        return parsed['address']
    
    def format_ist_time(datetime_obj, format_str="%d %b %Y, %I:%M %p"):
        return format_ist_datetime(datetime_obj, format_str)
    
    return dict(
        get_user_location=get_user_friendly_location,
        ist_now=ist_now,
        format_ist_time=format_ist_time,
        razorpay_key_id=RAZORPAY_KEY_ID
    )

# ============================================
# ✅ APPLICATION STARTUP
# ============================================

if __name__ == '__main__':
    is_render = os.environ.get('RENDER') is not None
    
    if not is_render:
        print("🚀 Starting in LOCAL DEVELOPMENT mode with Supabase")
        print(f"⏰ Current IST time: {ist_now().strftime('%d %b %Y, %I:%M %p')}")
        print(f"✅ Supabase URL: {SUPABASE_URL[:30]}...")
        print(f"✅ Supabase Key configured: {'Yes' if SUPABASE_KEY else 'No'}")
        
        try:
            test = supabase.table('users').select('*').limit(1).execute()
            print("✅ Supabase connection successful!")
        except Exception as e:
            print(f"⚠️ Supabase connection failed: {e}")
            print("⚠️ Please check your SUPABASE_URL and SUPABASE_KEY in .env file")
        
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        app.run(debug=True, host='0.0.0.0', port=5000)
    else:
        print("🚀 Starting in RENDER PRODUCTION mode with Supabase")
        print(f"⏰ Current IST time: {ist_now().strftime('%d %b %Y, %I:%M %p')}")
        print("✅ Application ready for gunicorn")
