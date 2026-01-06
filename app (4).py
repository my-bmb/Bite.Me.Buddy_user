# app.py
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

app = Flask(__name__, 
    template_folder='templates',  # ✅ Explicit template folder
    static_folder='static'        # ✅ Explicit static folder
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """Establish database connection using DATABASE_URL from environment"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Parse DATABASE_URL for psycopg
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    return psycopg.connect(database_url, row_factory=dict_row)

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
    """Home page - redirect to login or dashboard"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

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
        
        # Handle profile picture
        profile_pic = 'default-avatar.jpg'
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Generate unique filename
                ext = filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{secrets.token_hex(8)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                
                # Save file (without PIL resize)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                
                profile_pic = unique_filename
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
    """Display active services"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM services WHERE status = 'active' ORDER BY name"
                )
                services_list = cur.fetchall()
                
        return render_template('services.html', services=services_list)
    except Exception as e:
        flash(f'Error loading services: {str(e)}', 'error')
        return render_template('services.html', services=[])

@app.route('/menu')
@login_required
def menu():
    """Display active menu items"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM menu WHERE status = 'active' ORDER BY name"
                )
                menu_items = cur.fetchall()
                
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

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Order checkout and confirmation"""
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
                    # Get cart items and calculate total
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
                    
                    # Calculate total amount
                    total_amount = sum(float(item['price']) * item['quantity'] for item in cart_items)
                    
                    # Create order
                    cur.execute("""
                        INSERT INTO orders 
                        (user_id, total_amount, payment_mode, delivery_location, status)
                        VALUES (%s, %s, %s, %s, 'pending')
                        RETURNING order_id
                    """, (session['user_id'], total_amount, payment_mode, delivery_location))
                    
                    order = cur.fetchone()
                    order_id = order['order_id']
                    
                    # Create order items
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
                    
                    conn.commit()
                    
                    flash('Order placed successfully!', 'success')
                    return redirect(url_for('order_history'))
                    
        except Exception as e:
            flash(f'Error placing order: {str(e)}', 'error')
            return redirect(url_for('cart'))
    
    # GET request - show checkout form
    return render_template('checkout.html')

@app.route('/order_history')
@login_required
def order_history():
    """Display user's order history"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get orders
                cur.execute("""
                    SELECT * FROM orders 
                    WHERE user_id = %s 
                    ORDER BY order_date DESC
                """, (session['user_id'],))
                orders = cur.fetchall()
                
                # Get order items for each order
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
                
        return render_template('orders.html', orders=orders_with_items)
    except Exception as e:
        flash(f'Error loading order history: {str(e)}', 'error')
        return render_template('orders.html', orders=[])

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile view and edit"""
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
        
        # Handle profile picture
        profile_pic = session.get('profile_pic', 'default-avatar.jpg')
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                ext = filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{secrets.token_hex(8)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                
                # Delete old profile picture if not default
                if profile_pic != 'default-avatar.jpg':
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], profile_pic)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                profile_pic = unique_filename
        
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
    """Get service details for modal"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM services WHERE id = %s AND status = 'active'",
                    (service_id,)
                )
                service = cur.fetchone()
                
                if service:
                    return jsonify({
                        'success': True,
                        'service': {
                            'name': service['name'],
                            'photo': service['photo'],
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
    """Get menu item details for modal"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM menu WHERE id = %s AND status = 'active'",
                    (menu_id,)
                )
                menu_item = cur.fetchone()
                
                if menu_item:
                    return jsonify({
                        'success': True,
                        'menu': {
                            'name': menu_item['name'],
                            'photo': menu_item['photo'],
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
    # Create uploads directory if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Set default avatar if not exists
    default_avatar_path = os.path.join('static', 'default-avatar.jpg')
    if not os.path.exists(default_avatar_path):
        # Create a simple text file as placeholder
        with open(default_avatar_path, 'wb') as f:
            # You can add a pre-made default avatar image here
            pass
    
    app.run(debug=True, host='0.0.0.0', port=5000)