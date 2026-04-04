# app.py - COMPLETE UPDATED VERSION WITH SERVICE ORDER FIX
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
# ✅ FIXED TIMEZONE HELPER FUNCTIONS
# ============================================

def ist_now():
    """
    Returns current time in IST timezone
    """
    utc_now = datetime.now(UTC_TIMEZONE)
    return utc_now.astimezone(IST_TIMEZONE)

def utc_to_ist(utc_dt):
    """
    Convert UTC datetime to IST
    """
    if utc_dt is None:
        return None
    
    # Ensure it's timezone aware (UTC)
    if isinstance(utc_dt, str):
        utc_dt = parser.parse(utc_dt)
    
    if utc_dt.tzinfo is None:
        utc_dt = UTC_TIMEZONE.localize(utc_dt)
    
    return utc_dt.astimezone(IST_TIMEZONE)

def to_ist(datetime_obj):
    """
    Convert any datetime object to IST timezone safely
    Handles: None, string, naive datetime, UTC datetime
    """
    if datetime_obj is None:
        return None
    
    # ✅ FIXED: Agar string hai to datetime mein convert karo
    if isinstance(datetime_obj, str):
        try:
            datetime_obj = parser.parse(datetime_obj)
            print(f"✅ [to_ist] Converted string to datetime: {datetime_obj}")
        except Exception as e:
            print(f"⚠️ [to_ist] Could not parse string: {datetime_obj}")
            return datetime_obj
    
    # ✅ FIXED: Proper timezone handling
    try:
        # Agar already timezone aware hai
        if datetime_obj.tzinfo is not None:
            # Direct convert to IST
            return datetime_obj.astimezone(IST_TIMEZONE)
        else:
            # Naive datetime - assume UTC (standard practice)
            utc_dt = UTC_TIMEZONE.localize(datetime_obj)
            return utc_dt.astimezone(IST_TIMEZONE)
    except Exception as e:
        print(f"⚠️ [to_ist] Error converting: {e}")
        return datetime_obj

def format_ist_datetime(datetime_obj, format_str="%d %b %Y, %I:%M %p"):
    """
    Format datetime in IST with Indian 12-hour AM/PM format
    """
    if datetime_obj is None:
        return "Date not available"
    
    # ✅ FIXED: Agar string hai to pehle convert karo
    if isinstance(datetime_obj, str):
        try:
            datetime_obj = parser.parse(datetime_obj)
        except:
            return datetime_obj
    
    try:
        ist_time = to_ist(datetime_obj)
        if ist_time and hasattr(ist_time, 'strftime'):
            return ist_time.strftime(format_str)
        return str(datetime_obj)
    except Exception as e:
        print(f"⚠️ [format_ist_datetime] Error: {e}")
        return str(datetime_obj)

def debug_timezone(datetime_obj, source="unknown"):
    """Debug timezone issues"""
    print(f"\n🔍 TIMEZONE DEBUG [{source}]:")
    print(f"  Original: {datetime_obj}")
    print(f"  Type: {type(datetime_obj)}")
    if hasattr(datetime_obj, 'tzinfo'):
        print(f"  Has tzinfo: {datetime_obj.tzinfo is not None}")
        if datetime_obj.tzinfo:
            print(f"  Tzinfo: {datetime_obj.tzinfo}")
    ist_time = to_ist(datetime_obj)
    print(f"  IST: {ist_time}")
    if ist_time and hasattr(ist_time, 'strftime'):
        print(f"  Formatted: {ist_time.strftime('%d %b %Y, %I:%M %p')}")
    return ist_time

# ============================================
# ✅ ORDER ITEMS NORMALIZATION HELPER - ALWAYS RETURNS LIST
# ============================================

def normalize_order_items(raw_items):
    """
    Normalize order items to ALWAYS return a list of items.
    
    Handles:
    - JSON string → list
    - Python dict → list (single item)
    - Python list → list (already correct)
    - Invalid/empty data → empty list
    
    Returns:
        list: Normalized list of items, each with required fields
    """
    items_list = []
    
    if not raw_items:
        print("⚠️ [normalize_items] Empty or None items received")
        return items_list
    
    try:
        # Step 1: Parse JSON string if needed
        if isinstance(raw_items, str):
            # Check if it's empty string
            if not raw_items.strip():
                print("⚠️ [normalize_items] Empty JSON string")
                return items_list
                
            # Try to parse JSON
            try:
                json_items = json.loads(raw_items)
                print(f"✅ [normalize_items] Parsed JSON string, type: {type(json_items)}")
            except json.JSONDecodeError as e:
                print(f"❌ [normalize_items] JSON decode error: {e}")
                print(f"   Raw string: {raw_items[:200]}...")
                return items_list
        else:
            # Already a Python object
            json_items = raw_items
            print(f"✅ [normalize_items] Raw object type: {type(json_items)}")
        
        # Step 2: Normalize to list - CONVERT DICT TO LIST
        if isinstance(json_items, dict):
            # Single item as dict - convert to list
            print("⚠️ [normalize_items] Converting dict to list (single item)")
            json_items = [json_items]
        elif not isinstance(json_items, list):
            # Invalid type
            print(f"❌ [normalize_items] Invalid type after parsing: {type(json_items)}")
            return items_list
        
        # Step 3: Process each item with safe defaults
        print(f"📊 [normalize_items] Processing {len(json_items)} items")
        
        for idx, item in enumerate(json_items):
            if not isinstance(item, dict):
                print(f"⚠️ [normalize_items] Item {idx} is not dict, skipping")
                continue
            
            # Build normalized item with safe defaults
            normalized_item = {
                'name': item.get('item_name', item.get('name', 'Unknown Item')),
                'item_name': item.get('item_name', item.get('name', 'Unknown Item')),
                'type': item.get('item_type', item.get('type', 'unknown')),
                'item_type': item.get('item_type', item.get('type', 'unknown')),
                'item_id': item.get('item_id', item.get('id', 0)),
                'photo': item.get('item_photo', item.get('photo', '')),
                'item_photo': item.get('item_photo', item.get('photo', '')),
                'description': item.get('item_description', item.get('description', '')),
                'item_description': item.get('item_description', item.get('description', '')),
                'quantity': int(item.get('quantity', 1)),
                'price': float(item.get('price', 0)),
                'total': float(item.get('total', item.get('price', 0) * item.get('quantity', 1)))
            }
            
            items_list.append(normalized_item)
            print(f"  ✅ Item {idx}: {normalized_item['name']} (Type: {normalized_item['type']}, Qty: {normalized_item['quantity']})")
        
        print(f"✅ [normalize_items] Successfully normalized {len(items_list)} items")
        return items_list
        
    except Exception as e:
        print(f"❌ [normalize_items] Unexpected error: {e}")
        traceback.print_exc()
        return items_list


def format_items_for_storage(items_list):
    """
    Format items for database storage - ALWAYS returns JSON string of list
    
    Args:
        items_list: List of item dictionaries
    
    Returns:
        str: JSON string representation of items list
    """
    if not items_list:
        return json.dumps([])
    
    # Ensure it's a list
    if not isinstance(items_list, list):
        items_list = [items_list]
    
    # Standardize each item
    standardized_items = []
    for item in items_list:
        standardized_item = {
            'item_name': item.get('item_name', item.get('name', 'Unknown')),
            'item_type': item.get('item_type', item.get('type', 'unknown')),
            'item_id': int(item.get('item_id', item.get('id', 0))),
            'quantity': int(item.get('quantity', 1)),
            'price': float(item.get('price', 0)),
            'total': float(item.get('total', item.get('price', 0) * item.get('quantity', 1))),
            'item_photo': item.get('item_photo', item.get('photo', '')),
            'item_description': item.get('item_description', item.get('description', ''))
        }
        standardized_items.append(standardized_item)
    
    return json.dumps(standardized_items)

# ✅ FLASK APP SETUP
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static',
    static_url_path='/static'
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.permanent_session_lifetime = timedelta(days=7)

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

# ✅ DEFAULT URLS
DEFAULT_AVATAR_URL = "https://res.cloudinary.com/demo/image/upload/v1234567890/profile_pics/default-avatar.png"
SERVICES_FOLDER = "services"
GOODS_FOLDER = "goods_items"

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
# ✅ SUPABASE HELPER FUNCTIONS - Supabase v2.0+ COMPATIBLE
# ============================================

def get_supabase_client(use_admin=False):
    """Get Supabase client - use admin for write operations"""
    return supabase_admin if use_admin else supabase

def supabase_execute(table_name, operation='select', data=None, conditions=None, use_admin=True, limit=None):
    """
    Execute Supabase operations consistently - FIXED for Supabase v2.0+
    """
    client = get_supabase_client(use_admin)
    
    try:
        if operation == 'select':
            query = client.table(table_name).select('*')
            if conditions:
                for key, value in conditions.items():
                    if value is not None:
                        query = query.eq(key, value)
            if limit:
                query = query.limit(limit)
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
        print(f"   Conditions: {conditions}")
        print(f"   Data: {data}")
        raise

# ============================================
# ✅ PREFETCHING SYSTEM - PRELOAD PAGE URLs
# ============================================

def get_all_internal_urls():
    """
    Get all internal URLs for prefetching
    Returns list of URLs that should be preloaded
    """
    urls = []
    
    # Add main navigation URLs
    main_routes = ['dashboard', 'services', 'goods', 'cart', 'order_history', 'profile']
    
    for route in main_routes:
        try:
            urls.append(url_for(route))
        except Exception as e:
            print(f"⚠️ Could not generate URL for {route}: {e}")
    
    # Add dynamic URLs that are commonly accessed
    try:
        # Get all service collections
        collections = supabase_execute('service_collections', 'select', conditions={'status': 'active'}, use_admin=False)
        if collections:
            for collection in collections[:5]:
                try:
                    urls.append(url_for('service_collection_categories', collection_id=collection['id']))
                except:
                    pass
        
        # Get all goods collections
        goods_collections = supabase_execute('goods_collections', 'select', conditions={'status': 'active'}, use_admin=False)
        if goods_collections:
            for collection in goods_collections[:5]:
                try:
                    urls.append(url_for('goods_collection_categories', collection_id=collection['id']))
                except:
                    pass
                
    except Exception as e:
        print(f"⚠️ Could not prefetch dynamic URLs: {e}")
    
    return urls

@app.context_processor
def utility_processor():
    def get_user_friendly_location(location_string):
        parsed = parse_location_data(location_string)
        return parsed['address']
    
    def format_ist_time(datetime_obj, format_str="%d %b %Y, %I:%M %p"):
        """Format datetime in IST for Jinja templates"""
        return format_ist_datetime(datetime_obj, format_str)
    
    prefetch_urls = get_all_internal_urls()
    
    return dict(
        get_user_location=get_user_friendly_location,
        ist_now=ist_now,
        to_ist=to_ist,
        format_ist_time=format_ist_time,
        razorpay_key_id=RAZORPAY_KEY_ID,
        prefetch_urls=prefetch_urls
    )

# ============================================
# ✅ HIERARCHY HELPER FUNCTIONS
# ============================================

def get_service_hierarchy():
    """
    Get full service hierarchy: Collections → Categories → Services
    Returns list of collections with nested categories and services
    """
    try:
        collections = supabase_execute('service_collections', 'select', conditions={'status': 'active'}, use_admin=False)
        collections = sorted(collections, key=lambda x: x.get('position', 0)) if collections else []
        
        for collection in collections:
            categories = supabase_execute('service_categories', 'select', 
                                         conditions={'collection_id': collection['id'], 'status': 'active'},
                                         use_admin=False)
            categories = sorted(categories, key=lambda x: x.get('position', 0)) if categories else []
            
            for category in categories:
                services_list = supabase_execute('services', 'select',
                                           conditions={'category_id': category['id'], 'status': 'active'},
                                           use_admin=False)
                services_list = sorted(services_list, key=lambda x: x.get('position', 0)) if services_list else []
                
                for service in services_list:
                    if not service.get('photo'):
                        service['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
                
                category['services'] = services_list
                category['service_count'] = len(services_list)
                
                if not category.get('category_photo'):
                    category['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_service_category.jpg"
            
            collection['categories'] = categories
            collection['category_count'] = len(categories)
            
            if not collection.get('collection_photo'):
                collection['collection_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_service_collection.jpg"
        
        return collections
        
    except Exception as e:
        print(f"❌ [get_service_hierarchy] Error: {e}")
        traceback.print_exc()
        return []

def get_goods_hierarchy():
    """
    Get full goods hierarchy: Collections → Categories → Goods Items
    Returns list of collections with nested categories and items
    """
    try:
        collections = supabase_execute('goods_collections', 'select', conditions={'status': 'active'}, use_admin=False)
        collections = sorted(collections, key=lambda x: x.get('position', 0)) if collections else []
        
        for collection in collections:
            categories = supabase_execute('goods_categories', 'select',
                                         conditions={'collection_id': collection['id'], 'status': 'active'},
                                         use_admin=False)
            categories = sorted(categories, key=lambda x: x.get('position', 0)) if categories else []
            
            for category in categories:
                items_list = supabase_execute('goods_items', 'select',
                                           conditions={'category_id': category['id'], 'status': 'active'},
                                           use_admin=False)
                items_list = sorted(items_list, key=lambda x: x.get('position', 0)) if items_list else []
                
                for item in items_list:
                    if not item.get('photo'):
                        item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg"
                
                category['items'] = items_list
                category['item_count'] = len(items_list)
                
                if not category.get('category_photo'):
                    category['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_goods_category.jpg"
            
            collection['categories'] = categories
            collection['category_count'] = len(categories)
            
            if not collection.get('collection_photo'):
                collection['collection_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_goods_collection.jpg"
        
        return collections
        
    except Exception as e:
        print(f"❌ [get_goods_hierarchy] Error: {e}")
        traceback.print_exc()
        return []

def init_database():
    """Check Supabase connection - Tables already created in Supabase Dashboard"""
    print("🔗 Testing Supabase connection...")
    try:
        result = supabase.table('users').select('*').limit(1).execute()
        print("✅ Supabase connected successfully!")
        print("✅ Tables already exist in Supabase - no need to create")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print("⚠️ Please check your SUPABASE_URL and SUPABASE_KEY in .env file")
        raise

# ✅ AUTOMATIC DATABASE INITIALIZATION
print("🚀 Starting Bite Me Buddy Application with Supabase...")
try:
    init_database()
    print("✅ Supabase connection successful!")
except Exception as e:
    print(f"⚠️ Supabase connection failed: {e}")
    print("⚠️ Make sure SUPABASE_URL and SUPABASE_KEY are correct in .env file")

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
# ✅ AUTHENTICATION ROUTES - SUPABASE
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
                
                current_ist = ist_now()
                session['created_at'] = current_ist.strftime('%d %b %Y')
                session['created_at_raw'] = current_ist.isoformat()
                
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
            users = supabase_execute(
                'users',
                'select',
                conditions={'phone': phone}
            )
            
            if users and len(users) > 0:
                user = users[0]
                
                if check_password_hash(user['password'], password):
                    supabase_execute(
                        'users',
                        'update',
                        data={'last_login': 'now()'},
                        conditions={'id': user['id']},
                        use_admin=True
                    )
                    
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
                    
                    if user.get('created_at'):
                        try:
                            formatted_date = format_ist_datetime(user['created_at'], "%d %b %Y")
                            session['created_at'] = formatted_date
                            session['created_at_raw'] = str(user['created_at'])
                            print(f"✅ [LOGIN] Created_at formatted: {formatted_date}")
                        except Exception as e:
                            print(f"⚠️ [LOGIN] Date format error: {e}")
                            session['created_at'] = str(user['created_at']).split()[0] if user['created_at'] else 'Recently'
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
# ✅ DASHBOARD ROUTE
# ============================================

@app.route('/dashboard')
@login_required
def dashboard():
    """User Dashboard - Shows top discounts, new arrivals, collections, etc."""
    print("\n🔍 [DASHBOARD] Fetching user dashboard data...")
    
    try:
        top_discount_items = []
        
        services = supabase_execute('services', 'select', conditions={'status': 'active'}, use_admin=False)
        print(f"📊 [DASHBOARD] Found {len(services) if services else 0} total services")
        
        if services:
            service_count = 0
            for service in services:
                discount = service.get('discount', 0)
                if discount > 0:
                    service_count += 1
                    top_discount_items.append({
                        'id': service['id'],
                        'name': service['name'],
                        'type': 'service',
                        'photo': service.get('photo', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg'),
                        'price': float(service.get('price', 0)),
                        'discount': discount,
                        'final_price': float(service.get('final_price', 0)),
                        'url': url_for('service_details', service_id=service['id'])
                    })
            print(f"✅ [DASHBOARD] Services with discount: {service_count}")
        else:
            print("⚠️ [DASHBOARD] No services found in database!")
        
        goods_items = supabase_execute('goods_items', 'select', conditions={'status': 'active'}, use_admin=False)
        print(f"📊 [DASHBOARD] Found {len(goods_items) if goods_items else 0} total goods items")
        
        if goods_items:
            goods_count = 0
            for item in goods_items:
                discount = item.get('discount', 0)
                if discount > 0:
                    goods_count += 1
                    top_discount_items.append({
                        'id': item['id'],
                        'name': item['name'],
                        'type': 'goods',
                        'photo': item.get('photo', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg'),
                        'price': float(item.get('price', 0)),
                        'discount': discount,
                        'final_price': float(item.get('final_price', 0)),
                        'url': url_for('goods_item_details', item_id=item['id'])
                    })
            print(f"✅ [DASHBOARD] Goods items with discount: {goods_count}")
        else:
            print("⚠️ [DASHBOARD] No goods items found in database!")
        
        top_discount_items.sort(key=lambda x: x['discount'], reverse=True)
        top_discount_items = top_discount_items[:15]
        
        print(f"\n🔥 [DASHBOARD] FINAL DISCOUNT ITEMS: {len(top_discount_items)}")
        for item in top_discount_items:
            print(f"  - {item['type'].upper()}: {item['name']} | {item['discount']}% OFF")
        
        new_arrivals = []
        
        if services:
            latest_services = sorted(services, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
            for service in latest_services:
                new_arrivals.append({
                    'id': service['id'],
                    'name': service['name'],
                    'type': 'service',
                    'photo': service.get('photo', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg'),
                    'final_price': float(service.get('final_price', 0)),
                    'url': url_for('service_details', service_id=service['id']),
                    'added_date': format_ist_datetime(service.get('created_at'), "%d %b")
                })
        
        if goods_items:
            latest_goods = sorted(goods_items, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
            for item in latest_goods:
                new_arrivals.append({
                    'id': item['id'],
                    'name': item['name'],
                    'type': 'goods',
                    'photo': item.get('photo', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg'),
                    'final_price': float(item.get('final_price', 0)),
                    'url': url_for('goods_item_details', item_id=item['id']),
                    'added_date': format_ist_datetime(item.get('created_at'), "%d %b")
                })
        
        new_arrivals.sort(key=lambda x: x.get('added_date', ''), reverse=True)
        new_arrivals = new_arrivals[:12]
        
        print(f"📦 [DASHBOARD] New arrivals: {len(new_arrivals)} items")
        
        service_collections = supabase_execute('service_collections', 'select', conditions={'status': 'active'}, use_admin=False)
        if service_collections:
            service_collections = sorted(service_collections, key=lambda x: x.get('position', 0))
            print(f"📁 [DASHBOARD] Service collections: {len(service_collections)}")
        else:
            service_collections = []
        
        goods_collections = supabase_execute('goods_collections', 'select', conditions={'status': 'active'}, use_admin=False)
        if goods_collections:
            goods_collections = sorted(goods_collections, key=lambda x: x.get('position', 0))
            print(f"📁 [DASHBOARD] Goods collections: {len(goods_collections)}")
        else:
            goods_collections = []
        
        all_services = supabase_execute('services', 'select', conditions={'status': 'active'}, use_admin=False)
        if all_services:
            all_services = sorted(all_services, key=lambda x: x.get('position', 0))
            for service in all_services:
                if not service.get('photo'):
                    service['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
            print(f"🛎️ [DASHBOARD] All services: {len(all_services)}")
        else:
            all_services = []
        
        all_goods_items = supabase_execute('goods_items', 'select', conditions={'status': 'active'}, use_admin=False)
        if all_goods_items:
            all_goods_items = sorted(all_goods_items, key=lambda x: x.get('position', 0))
            for item in all_goods_items:
                if not item.get('photo'):
                    item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg"
            print(f"📦 [DASHBOARD] All goods items: {len(all_goods_items)}")
        else:
            all_goods_items = []
        
        trending_items = get_trending_items(limit=10)
        
        cart_items = supabase_execute('cart', 'select', conditions={'user_id': session['user_id']})
        cart_count = len(cart_items) if cart_items else 0
        
        cart_items_preview = []
        cart_total = 0
        if cart_items:
            for item in cart_items[:3]:
                if item['item_type'] == 'service':
                    details = supabase_execute('services', 'select', conditions={'id': item['item_id']})
                else:
                    details = supabase_execute('goods_items', 'select', conditions={'id': item['item_id']})
                
                if details:
                    details = details[0]
                    cart_items_preview.append({
                        'name': details['name'],
                        'type': item['item_type'],
                        'quantity': item['quantity'],
                        'photo': details.get('photo', ''),
                        'total': float(details['final_price']) * item['quantity']
                    })
                    cart_total += float(details['final_price']) * item['quantity']
        
        orders = supabase_execute('orders', 'select', conditions={'user_id': session['user_id']})
        order_count = len(orders) if orders else 0
        total_spent = sum(float(o.get('total_amount', 0)) for o in orders) if orders else 0
        pending_orders = sum(1 for o in orders if o.get('status') == 'pending') if orders else 0
        
        user_orders = []
        if orders:
            sorted_orders = sorted(orders, key=lambda x: x.get('order_date', ''), reverse=True)
            for i, order in enumerate(sorted_orders[:3]):
                customer_order_no = len(sorted_orders) - i
                items_count = 0
                if order.get('items'):
                    try:
                        items_list = json.loads(order['items'])
                        items_count = len(items_list)
                    except:
                        items_count = 0
                
                user_orders.append({
                    'order_id': order['order_id'],
                    'order_no': customer_order_no,
                    'total_amount': float(order.get('total_amount', 0)),
                    'status': order.get('status', 'pending'),
                    'order_date': format_ist_datetime(order.get('order_date'), "%d %b %Y"),
                    'items_count': items_count
                })
        
        user_addresses = supabase_execute('addresses', 'select', conditions={'user_id': session['user_id']})
        address_count = len(user_addresses) if user_addresses else 0
        
        notifications = supabase_execute('notifications', 'select', conditions={'user_id': session['user_id']})
        unread_count = sum(1 for n in notifications if not n.get('is_read')) if notifications else 0
        
        recent_notifications = []
        if notifications:
            sorted_notif = sorted(notifications, key=lambda x: x.get('created_at', ''), reverse=True)
            for notif in sorted_notif[:3]:
                recent_notifications.append({
                    'id': notif['id'],
                    'title': notif.get('title', ''),
                    'message': notif.get('message', ''),
                    'type': notif.get('type', 'info'),
                    'is_read': notif.get('is_read', False),
                    'created_at_formatted': format_ist_datetime(notif.get('created_at'), "%d %b, %I:%M %p")
                })
        
        if unread_count > 0:
            supabase_execute(
                'notifications',
                'update',
                data={'is_read': True, 'read_at': 'now()'},
                conditions={'user_id': session['user_id'], 'is_read': False},
                use_admin=True
            )
        
        max_discount = 0
        if top_discount_items:
            max_discount = max(item['discount'] for item in top_discount_items)
        
        print(f"\n✅ [DASHBOARD] Final Stats: {order_count} orders, {cart_count} cart items, ₹{total_spent} spent")
        
        return render_template('dashboard.html',
                             top_discount_items=top_discount_items,
                             new_arrivals=new_arrivals,
                             service_collections=service_collections,
                             goods_collections=goods_collections,
                             all_services=all_services,
                             all_goods_items=all_goods_items,
                             trending_items=trending_items,
                             cart_count=cart_count,
                             cart_items=cart_items_preview,
                             cart_total=cart_total,
                             order_count=order_count,
                             total_spent=total_spent,
                             pending_orders=pending_orders,
                             user_orders=user_orders,
                             user_addresses=user_addresses,
                             address_count=address_count,
                             recent_notifications=recent_notifications,
                             unread_count=unread_count,
                             max_discount=max_discount,
                             active_tab='dashboard')
        
    except Exception as e:
        print(f"❌ [DASHBOARD] Error: {e}")
        traceback.print_exc()
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html',
                             top_discount_items=[],
                             new_arrivals=[],
                             service_collections=[],
                             goods_collections=[],
                             all_services=[],
                             all_goods_items=[],
                             trending_items=[],
                             cart_count=0,
                             cart_items=[],
                             cart_total=0,
                             order_count=0,
                             total_spent=0,
                             pending_orders=0,
                             user_orders=[],
                             user_addresses=[],
                             address_count=0,
                             recent_notifications=[],
                             unread_count=0,
                             max_discount=0,
                             active_tab='dashboard')

# ============================================
# ✅ TRENDING ITEMS FUNCTION
# ============================================

def get_trending_items(limit=10):
    """
    Get trending items based on recent orders (last 30 days)
    Returns list of trending services and goods items
    """
    try:
        from datetime import datetime, timedelta
        
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        
        recent_orders = supabase_execute(
            'orders',
            'select',
            conditions={},
            use_admin=False
        )
        
        recent_orders = [o for o in recent_orders if o.get('order_date', '') > thirty_days_ago] if recent_orders else []
        
        item_count = {}
        item_details = {}
        
        for order in recent_orders:
            if order.get('items'):
                try:
                    items = json.loads(order['items'])
                    for item in items:
                        item_id = item.get('item_id')
                        item_type = item.get('item_type')
                        item_name = item.get('item_name', item.get('name', ''))
                        item_photo = item.get('item_photo', item.get('photo', ''))
                        item_price = item.get('price', 0)
                        
                        key = f"{item_type}_{item_id}"
                        
                        if key not in item_count:
                            item_count[key] = 0
                            if item_type == 'service':
                                url = url_for('service_details', service_id=item_id)
                            else:
                                url = url_for('goods_item_details', item_id=item_id)
                            
                            item_details[key] = {
                                'id': item_id,
                                'type': item_type,
                                'name': item_name,
                                'photo': item_photo,
                                'price': item_price,
                                'url': url
                            }
                        
                        item_count[key] += item.get('quantity', 1)
                        
                except Exception as e:
                    print(f"Error parsing order items: {e}")
        
        trending = sorted(item_count.items(), key=lambda x: x[1], reverse=True)
        
        trending_items = []
        for key, count in trending[:limit]:
            if key in item_details:
                details = item_details[key]
                details['order_count'] = count
                trending_items.append(details)
        
        print(f"✅ [TRENDING] Found {len(trending_items)} trending items")
        return trending_items
        
    except Exception as e:
        print(f"❌ [TRENDING] Error: {e}")
        traceback.print_exc()
        return []

# ============================================
# ✅ SERVICES SYSTEM - UPDATED WITH HIERARCHY + ACTIVE TAB
# ============================================

@app.route('/services')
@login_required
def services():
    """Display all service collections with categories and services (hierarchy view)"""
    print("\n🔍 [SERVICES] Fetching service hierarchy from Supabase...")
    try:
        collections = get_service_hierarchy()
        
        total_collections = len(collections)
        total_categories = sum(c.get('category_count', 0) for c in collections)
        total_services = sum(sum(cat.get('service_count', 0) for cat in c.get('categories', [])) for c in collections)
        
        print(f"✅ [SERVICES] Found {total_collections} collections, {total_categories} categories, {total_services} services")
        
        return render_template('services.html', 
                             collections=collections,
                             total_collections=total_collections,
                             total_categories=total_categories,
                             total_services=total_services,
                             active_tab='services')
        
    except Exception as e:
        print(f"❌ [SERVICES] Error loading service hierarchy: {e}")
        traceback.print_exc()
        flash('Error loading services', 'error')
        return render_template('services.html', collections=[], active_tab='services')

@app.route('/service-collection/<int:collection_id>')
@login_required
def service_collection_categories(collection_id):
    """Display all categories in a specific service collection with collection details"""
    print(f"\n🔍 [SERVICE-COLLECTION] Fetching collection ID: {collection_id}")
    try:
        collections = supabase_execute(
            'service_collections',
            'select',
            conditions={'id': collection_id, 'status': 'active'}
        )
        
        if not collections:
            flash('Collection not found', 'error')
            return redirect(url_for('services'))
        
        collection = collections[0]
        
        categories = supabase_execute(
            'service_categories',
            'select',
            conditions={'collection_id': collection_id, 'status': 'active'}
        )
        categories = sorted(categories, key=lambda x: x.get('position', 0)) if categories else []
        
        total_services = 0
        for category in categories:
            services_list = supabase_execute(
                'services',
                'select',
                conditions={'category_id': category['id'], 'status': 'active'}
            )
            category['service_count'] = len(services_list) if services_list else 0
            total_services += category['service_count']
            
            if not category.get('category_photo'):
                category['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_service_category.jpg"
        
        all_collections = get_service_hierarchy()
        
        if not collection.get('collection_photo'):
            collection['collection_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_service_collection.jpg"
        
        return render_template('service_collection_categories.html',
                             collection=collection,
                             categories=categories,
                             total_services=total_services,
                             all_collections=all_collections,
                             active_tab='services')
        
    except Exception as e:
        print(f"❌ [SERVICE-COLLECTION] Error: {e}")
        traceback.print_exc()
        flash('Error loading collection', 'error')
        return redirect(url_for('services'))

@app.route('/service-category-services/<int:category_id>')
@login_required
def service_category_services(category_id):
    """Display all services in a specific service category with category details"""
    print(f"\n🔍 [SERVICE-CATEGORY-SERVICES] Fetching category ID: {category_id}")
    try:
        categories = supabase_execute(
            'service_categories',
            'select',
            conditions={'id': category_id, 'status': 'active'}
        )
        
        if not categories:
            flash('Category not found', 'error')
            return redirect(url_for('services'))
        
        category = categories[0]
        
        collection_name = None
        if category.get('collection_id'):
            collections = supabase_execute(
                'service_collections',
                'select',
                conditions={'id': category['collection_id']}
            )
            if collections:
                collection_name = collections[0].get('name')
        
        services_list = supabase_execute(
            'services',
            'select',
            conditions={'category_id': category_id, 'status': 'active'}
        )
        services_list = sorted(services_list, key=lambda x: x.get('position', 0)) if services_list else []
        
        for service in services_list:
            if not service.get('photo'):
                service['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
        
        if not category.get('category_photo'):
            category['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_service_category.jpg"
        
        all_collections = get_service_hierarchy()
        
        all_categories = supabase_execute(
            'service_categories',
            'select',
            conditions={'status': 'active'}
        )
        
        if all_categories:
            all_categories = sorted(all_categories, key=lambda x: x.get('position', 0))
            print(f"📊 [SERVICE-CATEGORY-SERVICES] Found {len(all_categories)} total categories for sidebar")
            
            for cat in all_categories:
                if not cat.get('category_photo'):
                    cat['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_service_category.jpg"
        else:
            print(f"⚠️ [SERVICE-CATEGORY-SERVICES] No categories found in database")
            all_categories = []
        
        print(f"✅ [SERVICE-CATEGORY-SERVICES] Returning details for category: {category.get('name')}")
        print(f"✅ [SERVICE-CATEGORY-SERVICES] Sidebar categories count: {len(all_categories)}")
        
        return render_template('service_category_services.html',
                             category=category,
                             services=services_list,
                             collection_name=collection_name,
                             all_collections=all_collections,
                             all_categories=all_categories,
                             active_tab='services')
        
    except Exception as e:
        print(f"❌ [SERVICE-CATEGORY-SERVICES] Error: {e}")
        traceback.print_exc()
        flash('Error loading category services', 'error')
        return redirect(url_for('services'))

# ============================================
# ✅ API ENDPOINTS - GET CATEGORY SERVICES & GOODS
# ============================================

@app.route('/get_category_services/<int:category_id>')
@login_required
def get_category_services(category_id):
    """API endpoint to get all services for a specific category"""
    print(f"\n🔍 [API] Fetching services for category ID: {category_id}")
    try:
        services = supabase_execute(
            'services',
            'select',
            conditions={'category_id': category_id, 'status': 'active'},
            use_admin=False
        )
        
        if services:
            services = sorted(services, key=lambda x: x.get('position', 0))
        
        services_data = []
        for service in services:
            services_data.append({
                'id': service['id'],
                'name': service.get('name', ''),
                'photo': service.get('photo', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg'),
                'price': float(service.get('price', 0)),
                'discount': service.get('discount', 0),
                'final_price': float(service.get('final_price', 0)),
                'description': service.get('description', '')
            })
        
        print(f"✅ [API] Found {len(services_data)} services for category {category_id}")
        return jsonify({'success': True, 'services': services_data})
        
    except Exception as e:
        print(f"❌ [API] Error fetching category services: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e), 'services': []}), 500

@app.route('/get_goods_category_items/<int:category_id>')
@login_required
def get_goods_category_items(category_id):
    """API endpoint to get all goods items for a specific goods category"""
    print(f"\n🔍 [API] Fetching goods items for category ID: {category_id}")
    try:
        goods_items = supabase_execute(
            'goods_items',
            'select',
            conditions={'category_id': category_id, 'status': 'active'},
            use_admin=False
        )
        
        if goods_items:
            goods_items = sorted(goods_items, key=lambda x: x.get('position', 0))
        
        items_data = []
        for item in goods_items:
            items_data.append({
                'id': item['id'],
                'name': item.get('name', ''),
                'photo': item.get('photo', 'https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg'),
                'price': float(item.get('price', 0)),
                'discount': item.get('discount', 0),
                'final_price': float(item.get('final_price', 0)),
                'description': item.get('description', '')
            })
        
        print(f"✅ [API] Found {len(items_data)} goods items for category {category_id}")
        return jsonify({'success': True, 'items': items_data})
        
    except Exception as e:
        print(f"❌ [API] Error fetching goods category items: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e), 'items': []}), 500

# ============================================
# ✅ SERVICE DETAIL ROUTE - WITH CATEGORY SERVICES
# ============================================

@app.route('/service-detail/<int:service_id>')
@login_required
def service_details(service_id):
    """Display detailed view of a single service with ALL columns and recommendations"""
    print(f"\n🔍 [SERVICE-DETAIL] Fetching service details for ID: {service_id}")
    try:
        services_list = supabase_execute(
            'services',
            'select',
            conditions={'id': service_id, 'status': 'active'}
        )
        
        if not services_list:
            print(f"❌ [SERVICE-DETAIL] Service {service_id} not found")
            flash('Service not found', 'error')
            return redirect(url_for('services'))
        
        service = services_list[0]
        print(f"📊 [SERVICE-DETAIL] Service: {service.get('name')}")
        print(f"📊 [SERVICE-DETAIL] Service columns: {list(service.keys())}")
        print(f"📊 [SERVICE-DETAIL] Price: {service.get('price', 0)} - Discount: {service.get('discount', 0)}% - Final: {service.get('final_price', 0)}")
        
        if not service.get('photo') or service['photo'] == '':
            try:
                search_name = service['name'].lower().replace(' ', '_')
                search_result = cloudinary.Search()\
                    .expression(f"folder:services AND filename:{search_name}*")\
                    .execute()
                
                if search_result['resources']:
                    service['photo'] = search_result['resources'][0]['secure_url']
                    print(f"  📸 Loaded Cloudinary photo for {service['name']}")
                else:
                    service['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
            except Exception as e:
                print(f"⚠️ Cloudinary error: {e}")
                service['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
        
        category = None
        if service.get('category_id'):
            categories = supabase_execute(
                'service_categories',
                'select',
                conditions={'id': service['category_id']}
            )
            if categories:
                category = categories[0]
                print(f"📊 [SERVICE-DETAIL] Category: {category.get('name')}")
                print(f"📊 [SERVICE-DETAIL] Category columns: {list(category.keys())}")
                if not category.get('category_photo'):
                    category['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_service_category.jpg"
        
        category_services = []
        if category:
            all_category_services = supabase_execute(
                'services',
                'select',
                conditions={'category_id': category['id'], 'status': 'active'}
            )
            category_services = [s for s in all_category_services if s['id'] != service_id]
            category_services = sorted(category_services, key=lambda x: x.get('position', 0))
            
            for cat_service in category_services:
                if not cat_service.get('photo') or cat_service['photo'] == '':
                    cat_service['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
        
        print(f"📊 [SERVICE-DETAIL] Found {len(category_services)} other services in same category")
        
        all_categories_list = supabase_execute(
            'service_categories',
            'select',
            conditions={'status': 'active'}
        )
        
        all_categories_with_services = []
        for cat in all_categories_list:
            services_list = supabase_execute(
                'services',
                'select',
                conditions={'category_id': cat['id'], 'status': 'active'}
            )
            services_list = sorted(services_list, key=lambda x: x.get('position', 0)) if services_list else []
            
            for service_item in services_list:
                if not service_item.get('photo') or service_item['photo'] == '':
                    service_item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_service.jpg"
            
            if not cat.get('category_photo'):
                cat['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_service_category.jpg"
            
            all_categories_with_services.append({
                'category': cat,
                'services': services_list
            })
        
        print(f"📊 [SERVICE-DETAIL] Found {len(all_categories_with_services)} categories with their services")
        
        all_collections = get_service_hierarchy()
        
        print(f"✅ [SERVICE-DETAIL] Returning details for service: {service.get('name')}")
        return render_template('service_details.html', 
                             service=service,
                             category=category,
                             category_services=category_services,
                             all_categories_with_services=all_categories_with_services,
                             all_collections=all_collections,
                             active_tab='services')
        
    except Exception as e:
        print(f"❌ [SERVICE-DETAIL] Error loading service details: {e}")
        traceback.print_exc()
        flash('Error loading service details', 'error')
        return redirect(url_for('services'))

# ============================================
# ✅ GOODS SYSTEM - UPDATED WITH HIERARCHY + ACTIVE TAB
# ============================================

@app.route('/goods')
@login_required
def goods():
    """Display all goods collections with categories and items (hierarchy view)"""
    print("\n🔍 [GOODS] Fetching goods hierarchy from Supabase...")
    try:
        collections = get_goods_hierarchy()
        
        total_collections = len(collections)
        total_categories = sum(c.get('category_count', 0) for c in collections)
        total_items = sum(sum(cat.get('item_count', 0) for cat in c.get('categories', [])) for c in collections)
        
        print(f"✅ [GOODS] Found {total_collections} collections, {total_categories} categories, {total_items} items")
        
        return render_template('goods.html', 
                             collections=collections,
                             total_collections=total_collections,
                             total_categories=total_categories,
                             total_items=total_items,
                             active_tab='goods')
        
    except Exception as e:
        print(f"❌ [GOODS] Error loading goods hierarchy: {e}")
        traceback.print_exc()
        flash('Error loading goods', 'error')
        return render_template('goods.html', collections=[], active_tab='goods')

@app.route('/goods-collection/<int:collection_id>')
@login_required
def goods_collection_categories(collection_id):
    """Display all categories in a specific goods collection with collection details"""
    print(f"\n🔍 [GOODS-COLLECTION] Fetching collection ID: {collection_id}")
    try:
        collections = supabase_execute(
            'goods_collections',
            'select',
            conditions={'id': collection_id, 'status': 'active'}
        )
        
        if not collections:
            flash('Collection not found', 'error')
            return redirect(url_for('goods'))
        
        collection = collections[0]
        
        categories = supabase_execute(
            'goods_categories',
            'select',
            conditions={'collection_id': collection_id, 'status': 'active'}
        )
        categories = sorted(categories, key=lambda x: x.get('position', 0)) if categories else []
        
        total_items = 0
        for category in categories:
            items_list = supabase_execute(
                'goods_items',
                'select',
                conditions={'category_id': category['id'], 'status': 'active'}
            )
            category['item_count'] = len(items_list) if items_list else 0
            total_items += category['item_count']
            
            if not category.get('category_photo'):
                category['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_goods_category.jpg"
        
        all_collections = get_goods_hierarchy()
        
        if not collection.get('collection_photo'):
            collection['collection_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_goods_collection.jpg"
        
        return render_template('goods_collection_categories.html',
                             collection=collection,
                             categories=categories,
                             total_items=total_items,
                             all_collections=all_collections,
                             active_tab='goods')
        
    except Exception as e:
        print(f"❌ [GOODS-COLLECTION] Error: {e}")
        traceback.print_exc()
        flash('Error loading collection', 'error')
        return redirect(url_for('goods'))

@app.route('/goods-category-items/<int:category_id>')
@login_required
def goods_category_items(category_id):
    """Display all goods items in a specific goods category with category details"""
    print(f"\n🔍 [GOODS-CATEGORY-ITEMS] Fetching category ID: {category_id}")
    try:
        categories = supabase_execute(
            'goods_categories',
            'select',
            conditions={'id': category_id, 'status': 'active'}
        )
        
        if not categories:
            flash('Category not found', 'error')
            return redirect(url_for('goods'))
        
        category = categories[0]
        
        collection_name = None
        if category.get('collection_id'):
            collections = supabase_execute(
                'goods_collections',
                'select',
                conditions={'id': category['collection_id']}
            )
            if collections:
                collection_name = collections[0].get('name')
        
        goods_items = supabase_execute(
            'goods_items',
            'select',
            conditions={'category_id': category_id, 'status': 'active'}
        )
        goods_items = sorted(goods_items, key=lambda x: x.get('position', 0)) if goods_items else []
        
        for item in goods_items:
            if not item.get('photo'):
                item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg"
        
        if not category.get('category_photo'):
            category['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_goods_category.jpg"
        
        all_collections = get_goods_hierarchy()
        
        all_categories = supabase_execute(
            'goods_categories',
            'select',
            conditions={'status': 'active'}
        )
        
        if all_categories:
            all_categories = sorted(all_categories, key=lambda x: x.get('position', 0))
            print(f"📊 [GOODS-CATEGORY-ITEMS] Found {len(all_categories)} total categories for sidebar")
            
            for cat in all_categories:
                if not cat.get('category_photo'):
                    cat['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_goods_category.jpg"
        else:
            all_categories = []
        
        return render_template('goods_category_items.html',
                             category=category,
                             goods_items=goods_items,
                             collection_name=collection_name,
                             all_collections=all_collections,
                             all_categories=all_categories,
                             active_tab='goods')
        
    except Exception as e:
        print(f"❌ [GOODS-CATEGORY-ITEMS] Error: {e}")
        traceback.print_exc()
        flash('Error loading category items', 'error')
        return redirect(url_for('goods'))

# ============================================
# ✅ GOODS ITEM DETAIL ROUTE - WITH CATEGORY ITEMS
# ============================================

@app.route('/goods-item/<int:item_id>')
@login_required
def goods_item_details(item_id):
    """Display detailed view of a single goods item with ALL columns and recommendations"""
    print(f"\n🔍 [GOODS-ITEM] Fetching goods item details for ID: {item_id}")
    try:
        goods_items = supabase_execute(
            'goods_items',
            'select',
            conditions={'id': item_id, 'status': 'active'}
        )
        
        if not goods_items:
            print(f"❌ [GOODS-ITEM] Goods item {item_id} not found")
            flash('Goods item not found', 'error')
            return redirect(url_for('goods'))
        
        goods_item = goods_items[0]
        print(f"📊 [GOODS-ITEM] Item: {goods_item.get('name')}")
        print(f"📊 [GOODS-ITEM] Goods item columns: {list(goods_item.keys())}")
        print(f"📊 [GOODS-ITEM] Price: {goods_item.get('price', 0)} - Discount: {goods_item.get('discount', 0)}% - Final: {goods_item.get('final_price', 0)}")
        
        if not goods_item.get('photo') or goods_item['photo'] == '':
            try:
                search_name = goods_item['name'].lower().replace(' ', '_')
                search_result = cloudinary.Search()\
                    .expression(f"folder:goods_items AND filename:{search_name}*")\
                    .execute()
                
                if search_result['resources']:
                    goods_item['photo'] = search_result['resources'][0]['secure_url']
                    print(f"  📸 Loaded Cloudinary photo for {goods_item['name']}")
                else:
                    goods_item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg"
            except Exception as e:
                print(f"⚠️ Cloudinary error: {e}")
                goods_item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg"
        
        category = None
        if goods_item.get('category_id'):
            categories = supabase_execute(
                'goods_categories',
                'select',
                conditions={'id': goods_item['category_id']}
            )
            if categories:
                category = categories[0]
                print(f"📊 [GOODS-ITEM] Category: {category.get('name')}")
                print(f"📊 [GOODS-ITEM] Category columns: {list(category.keys())}")
                if not category.get('category_photo'):
                    category['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_goods_category.jpg"
        
        category_items = []
        if category:
            all_category_items = supabase_execute(
                'goods_items',
                'select',
                conditions={'category_id': category['id'], 'status': 'active'}
            )
            category_items = [i for i in all_category_items if i['id'] != item_id]
            category_items = sorted(category_items, key=lambda x: x.get('position', 0))
            
            for cat_item in category_items:
                if not cat_item.get('photo') or cat_item['photo'] == '':
                    cat_item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg"
        
        print(f"📊 [GOODS-ITEM] Found {len(category_items)} other items in same category")
        
        all_categories_list = supabase_execute(
            'goods_categories',
            'select',
            conditions={'status': 'active'}
        )
        
        all_categories_with_items = []
        for cat in all_categories_list:
            items_list = supabase_execute(
                'goods_items',
                'select',
                conditions={'category_id': cat['id'], 'status': 'active'}
            )
            items_list = sorted(items_list, key=lambda x: x.get('position', 0)) if items_list else []
            
            for item in items_list:
                if not item.get('photo') or item['photo'] == '':
                    item['photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg"
            
            if not cat.get('category_photo'):
                cat['category_photo'] = "https://res.cloudinary.com/demo/image/upload/v1633427556/default_goods_category.jpg"
            
            all_categories_with_items.append({
                'category': cat,
                'items': items_list
            })
        
        print(f"📊 [GOODS-ITEM] Found {len(all_categories_with_items)} categories with their items")
        
        all_collections = get_goods_hierarchy()
        
        print(f"✅ [GOODS-ITEM] Returning details for item: {goods_item.get('name')}")
        return render_template('goods_item_details.html', 
                             goods_item=goods_item,
                             category=category,
                             category_items=category_items,
                             all_categories_with_items=all_categories_with_items,
                             all_collections=all_collections,
                             active_tab='goods')
        
    except Exception as e:
        print(f"❌ [GOODS-ITEM] Error loading goods details: {e}")
        traceback.print_exc()
        flash('Error loading goods details', 'error')
        return redirect(url_for('goods'))

# ============================================
# ✅ CART ROUTES - SUPABASE (FIXED)
# ============================================

@app.route('/cart')
@login_required
def cart():
    try:
        # Get cart items from Supabase
        cart_items_db = supabase_execute(
            'cart',
            'select',
            conditions={'user_id': session['user_id']}
        )
        
        cart_items = []
        total_amount = 0
        
        for item in cart_items_db:
            # Initialize variables with default values
            db_photo = ''
            item_name = ''
            item_price = 0
            item_description = ''
            
            if item['item_type'] == 'service':
                service_data = supabase_execute(
                    'services',
                    'select',
                    conditions={'id': item['item_id']}
                )
                if service_data:
                    service = service_data[0]
                    item_name = service['name']
                    item_price = float(service['final_price'])
                    item_description = service.get('description', '')
                    db_photo = service.get('photo', '')
            else:
                goods_data = supabase_execute(
                    'goods_items',
                    'select',
                    conditions={'id': item['item_id']}
                )
                if goods_data:
                    goods = goods_data[0]
                    item_name = goods['name']
                    item_price = float(goods['final_price'])
                    item_description = goods.get('description', '')
                    db_photo = goods.get('photo', '')
            
            # Skip if item not found (should not happen)
            if not item_name:
                continue
            
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
        
        return render_template('cart.html', cart_items=cart_items, total_amount=total_amount, active_tab='cart')
        
    except Exception as e:
        print(f"❌ Cart error: {e}")
        traceback.print_exc()
        flash(f'Error loading cart: {str(e)}', 'error')
        return render_template('cart.html', cart_items=[], total_amount=0, active_tab='cart')

def get_cloudinary_photo_for_cart(item_type, item_id, item_name):
    try:
        folder = SERVICES_FOLDER if item_type == 'service' else GOODS_FOLDER
        
        # Check Supabase first
        if item_type == 'service':
            service = supabase_execute('services', 'select', conditions={'id': item_id})
            if service and service[0].get('photo') and service[0]['photo'].startswith('http'):
                return service[0]['photo']
        else:
            goods_item = supabase_execute('goods_items', 'select', conditions={'id': item_id})
            if goods_item and goods_item[0].get('photo') and goods_item[0]['photo'].startswith('http'):
                return goods_item[0]['photo']
        
        # Search Cloudinary
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
        return "https://res.cloudinary.com/demo/image/upload/v1633427556/sample_goods.jpg"

@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    item_type = request.form.get('item_type')
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity', 1))
    
    if not item_type or not item_id:
        return jsonify({'success': False, 'message': 'Missing item information'})
    
    if item_type not in ['service', 'goods']:
        return jsonify({'success': False, 'message': 'Invalid item type'})
    
    try:
        # Check if item exists in Supabase
        if item_type == 'service':
            item_exists = supabase_execute(
                'services',
                'select',
                conditions={'id': item_id, 'status': 'active'}
            )
        else:
            item_exists = supabase_execute(
                'goods_items',
                'select',
                conditions={'id': item_id, 'status': 'active'}
            )
        
        if not item_exists:
            return jsonify({'success': False, 'message': 'Item not available'})
        
        # Check if already in cart
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
            # Update quantity
            new_quantity = existing[0]['quantity'] + quantity
            supabase_execute(
                'cart',
                'update',
                data={'quantity': new_quantity},
                conditions={'id': existing[0]['id']},
                use_admin=True
            )
        else:
            # Insert new cart item
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
        # Get cart item from Supabase
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
# ✅ CHECKOUT ROUTE - FIXED WITH PROPER FIELD NAMES
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
            flash('Payment mode and delivery location are required', 'error')
            return redirect(url_for('cart'))
        
        try:
            # Get cart items from Supabase
            cart_items = supabase_execute(
                'cart',
                'select',
                conditions={'user_id': session['user_id']}
            )
            
            if not cart_items:
                flash('Your cart is empty', 'error')
                return redirect(url_for('cart'))
            
            # Calculate total and get item details
            total_amount = 0
            items_list = []  # ✅ ALWAYS a LIST with PROPER FIELD NAMES
            
            for item in cart_items:
                if item['item_type'] == 'service':
                    details = supabase_execute(
                        'services',
                        'select',
                        conditions={'id': item['item_id']}
                    )
                else:
                    details = supabase_execute(
                        'goods_items',
                        'select',
                        conditions={'id': item['item_id']}
                    )
                
                if details:
                    details = details[0]
                    item_price = float(details['final_price'])
                    item_total = item_price * item['quantity']
                    total_amount += item_total
                    
                    # ✅ FIXED: Use item_name, item_photo, item_description (like prana wala)
                    items_list.append({
                        'item_type': item['item_type'],
                        'item_id': item['item_id'],
                        'item_name': details['name'],                    # ✅ 'item_name' not 'name'
                        'item_photo': details.get('photo', ''),          # ✅ 'item_photo' not 'photo'
                        'item_description': details.get('description', ''),  # ✅ 'item_description'
                        'quantity': item['quantity'],
                        'price': item_price,
                        'total': item_total
                    })
            
            # ✅ ALWAYS store as JSON string of LIST
            items_json = json.dumps(items_list)
            
            # Create order
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
                'status': 'pending' if payment_mode == 'cod' else 'pending_payment'
            }
            
            new_order = supabase_execute('orders', 'insert', data=order_data, use_admin=True)
            
            if not new_order:
                raise Exception("Failed to create order")
            
            order_id = new_order[0]['order_id']
            
            # Create payment record
            payment_data = {
                'order_id': order_id,
                'user_id': session['user_id'],
                'amount': total_amount,
                'payment_mode': payment_mode,
                'payment_status': 'pending'
            }
            
            supabase_execute('payments', 'insert', data=payment_data, use_admin=True)
            
            # Clear cart
            supabase_execute(
                'cart',
                'delete',
                conditions={'user_id': session['user_id']},
                use_admin=True
            )
            
            flash('Order placed successfully!', 'success')
            return redirect(url_for('order_history'))
                    
        except Exception as e:
            print(f"❌ [CHECKOUT ERROR] {str(e)}")
            traceback.print_exc()
            flash(f'Error placing order: {str(e)}', 'error')
            return redirect(url_for('cart'))
    
    # GET REQUEST: Show checkout page
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
                    'goods_items',
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
        cart_items_list = []
        cart_total = 0
        print(f"⚠️ [CHECKOUT GET ERROR] {e}")
    
    return render_template('checkout.html', 
                         cart_items=cart_items_list, 
                         cart_total=cart_total,
                         razorpay_key_id=RAZORPAY_KEY_ID,
                         active_tab='cart')

# ============================================
# ✅ ORDER HISTORY ROUTE - USING NORMALIZE FUNCTION
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
                    ist_time = to_ist(order['order_date'])
                    order['order_date_formatted'] = ist_time.strftime("%d %b %Y, %I:%M %p") if ist_time else "Date error"
                except Exception as e:
                    order['order_date_formatted'] = str(order['order_date'])
            else:
                order['order_date_formatted'] = 'Date not available'
            
            if order.get('delivery_date'):
                try:
                    ist_time = to_ist(order['delivery_date'])
                    order['delivery_date_formatted'] = ist_time.strftime("%d %b %Y, %I:%M %p") if ist_time else None
                except Exception as e:
                    order['delivery_date_formatted'] = str(order['delivery_date'])
            
            # ✅ Use normalize_items helper - ALWAYS returns list
            items_list = normalize_order_items(order.get('items'))
            
            # Get payment status
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
        
        return render_template('orders.html', orders=orders_list or [], active_tab='orders')
        
    except Exception as e:
        print(f"❌ [ORDER_HISTORY ERROR] {str(e)}")
        traceback.print_exc()
        flash(f'Error loading order history: {str(e)}', 'error')
        return render_template('orders.html', orders=[], active_tab='orders')

# ============================================
# ✅ ORDER DETAILS ROUTE - FIXED FOR BOTH SERVICE AND GOODS
# ============================================

@app.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    """View detailed order information - FIXED for both service and goods orders"""
    try:
        print(f"\n🔍 [ORDER_DETAILS] STARTING for order_id: {order_id}")
        
        orders = supabase_execute(
            'orders',
            'select',
            conditions={'order_id': order_id, 'user_id': session['user_id']}
        )
        
        if not orders:
            flash('Order not found', 'error')
            return redirect(url_for('order_history'))
        
        order = orders[0]
        
        # Get order number
        all_user_orders = supabase_execute(
            'orders',
            'select',
            conditions={'user_id': session['user_id']}
        )
        all_user_orders = sorted(all_user_orders, key=lambda x: x.get('order_date', ''), reverse=True) if all_user_orders else []
        
        customer_order_no = None
        for index, user_order in enumerate(all_user_orders):
            if user_order['order_id'] == order_id:
                customer_order_no = len(all_user_orders) - index
                break
        
        if customer_order_no is None:
            customer_order_no = 1
        
        # Format dates
        if order.get('order_date'):
            try:
                ist_time = to_ist(order['order_date'])
                order['order_date_formatted'] = ist_time.strftime("%d %b %Y, %I:%M %p") if ist_time else "Date error"
            except Exception as e:
                order['order_date_formatted'] = str(order['order_date'])
        else:
            order['order_date_formatted'] = 'Date not available'
        
        if order.get('delivery_date'):
            try:
                ist_time = to_ist(order['delivery_date'])
                order['delivery_date_formatted'] = ist_time.strftime("%d %b %Y, %I:%M %p") if ist_time else None
            except Exception as e:
                order['delivery_date_formatted'] = str(order['delivery_date'])
        
        # Get payment details
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
                if payment.get('payment_date'):
                    try:
                        ist_time = to_ist(payment['payment_date'])
                        order['payment_date_formatted'] = ist_time.strftime("%d %b %Y, %I:%M %p") if ist_time else None
                    except Exception as e:
                        order['payment_date_formatted'] = str(payment['payment_date'])
        except Exception as e:
            print(f"⚠️ Payment details error: {e}")
            order['payment_status'] = order.get('payment_mode', 'pending')
        
        # ✅ CRITICAL FIX: Parse items properly for BOTH service and goods
        items_list = []
        
        if order.get('items'):
            try:
                if isinstance(order['items'], str):
                    json_items = json.loads(order['items'])
                else:
                    json_items = order['items']
                
                if isinstance(json_items, dict):
                    json_items = [json_items]
                
                if isinstance(json_items, list):
                    for item in json_items:
                        # Get item_type (handle both 'item_type' and 'type')
                        item_type = item.get('item_type', item.get('type', 'unknown'))
                        item_id = item.get('item_id')
                        
                        # Get fields (handle both naming conventions)
                        item_name = item.get('item_name', item.get('name', 'Unknown Item'))
                        item_photo = item.get('item_photo', item.get('photo', ''))
                        item_description = item.get('item_description', item.get('description', ''))
                        item_price = float(item.get('price', 0))
                        item_quantity = int(item.get('quantity', 1))
                        
                        # Try to fetch fresh details from database
                        if item_type == 'service' and item_id:
                            try:
                                db_item = supabase_execute(
                                    'services',
                                    'select',
                                    conditions={'id': item_id, 'status': 'active'}
                                )
                                if db_item:
                                    db_item = db_item[0]
                                    item_name = db_item.get('name', item_name)
                                    item_photo = db_item.get('photo', item_photo)
                                    item_description = db_item.get('description', item_description)
                                    item_price = float(db_item.get('final_price', item_price))
                                    print(f"  ✅ Fetched fresh service data for ID {item_id}")
                            except Exception as e:
                                print(f"  ⚠️ Could not fetch service: {e}")
                                
                        elif item_type == 'goods' and item_id:
                            try:
                                db_item = supabase_execute(
                                    'goods_items',
                                    'select',
                                    conditions={'id': item_id, 'status': 'active'}
                                )
                                if db_item:
                                    db_item = db_item[0]
                                    item_name = db_item.get('name', item_name)
                                    item_photo = db_item.get('photo', item_photo)
                                    item_description = db_item.get('description', item_description)
                                    item_price = float(db_item.get('final_price', item_price))
                                    print(f"  ✅ Fetched fresh goods data for ID {item_id}")
                            except Exception as e:
                                print(f"  ⚠️ Could not fetch goods: {e}")
                        
                        items_list.append({
                            'name': item_name,
                            'item_name': item_name,
                            'type': item_type,
                            'item_type': item_type,
                            'item_id': item_id,
                            'photo': item_photo,
                            'item_photo': item_photo,
                            'description': item_description,
                            'item_description': item_description,
                            'quantity': item_quantity,
                            'price': item_price,
                            'total': item_price * item_quantity
                        })
                        print(f"  ✅ Added item: {item_name} (Type: {item_type}, Qty: {item_quantity})")
                        
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                items_list = []
            except Exception as e:
                print(f"❌ Error parsing items: {e}")
                traceback.print_exc()
                items_list = []
        
        order['order_no'] = customer_order_no
        
        print(f"\n✅ [ORDER_DETAILS] Final - Items Count: {len(items_list)}")
        
        return render_template('order_details.html', 
                             order=order, 
                             items=items_list,
                             active_tab='orders')
                
    except Exception as e:
        print(f"❌ [ORDER_DETAILS ERROR] {str(e)}")
        traceback.print_exc()
        flash(f'Error loading order details: {str(e)}', 'error')
        return redirect(url_for('order_history'))

# ============================================
# ✅ ORDERS REDIRECT ROUTE
# ============================================

@app.route('/orders')
@login_required
def orders():
    return redirect(url_for('order_history'))

# ============================================
# ✅ PROFILE ROUTES - SUPABASE
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
    
    return render_template('profile.html', active_tab='profile')

# ============================================
# ✅ ADDRESS ROUTES - SUPABASE
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
# ✅ NOTIFICATIONS ROUTES - SUPABASE
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
        
        return jsonify({'success': True, 'message': 'Order cancelled successfully'})
                
    except Exception as e:
        print(f"❌ [CANCEL_ORDER ERROR] {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================
# ✅ AFTER REQUEST HANDLER
# ============================================

@app.after_request
def after_request(response):
    session.modified = True
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

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
