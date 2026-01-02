# init_db.py
import os
import sys
import psycopg

def get_db_connection():
    """Establish database connection using DATABASE_URL from environment"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("Error: DATABASE_URL environment variable is not set")
        sys.exit(1)
    
    # Parse DATABASE_URL for psycopg
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    return psycopg.connect(database_url)

def create_tables():
    """Create all database tables"""
    print("Creating database tables...")
    
    sql_commands = [
        # Users table
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            profile_pic VARCHAR(255),
            full_name VARCHAR(100) NOT NULL,
            phone VARCHAR(15) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            location TEXT NOT NULL,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        
        # Services table
        """
        CREATE TABLE IF NOT EXISTS services (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            photo VARCHAR(255),
            price DECIMAL(10, 2) NOT NULL,
            discount DECIMAL(10, 2) DEFAULT 0,
            final_price DECIMAL(10, 2) NOT NULL,
            description TEXT,
            status VARCHAR(20) DEFAULT 'active'
        );
        """,
        
        # Menu table
        """
        CREATE TABLE IF NOT EXISTS menu (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            photo VARCHAR(255),
            price DECIMAL(10, 2) NOT NULL,
            discount DECIMAL(10, 2) DEFAULT 0,
            final_price DECIMAL(10, 2) NOT NULL,
            description TEXT,
            status VARCHAR(20) DEFAULT 'active'
        );
        """,
        
        # Cart table
        """
        CREATE TABLE IF NOT EXISTS cart (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            item_type VARCHAR(10) CHECK (item_type IN ('service', 'menu')),
            item_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            UNIQUE(user_id, item_type, item_id)
        );
        """,
        
        # Orders table
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            total_amount DECIMAL(10, 2) NOT NULL,
            payment_mode VARCHAR(20) NOT NULL,
            delivery_location TEXT NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'pending'
        );
        """,
        
        # Order items table
        """
        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
            item_type VARCHAR(10) CHECK (item_type IN ('service', 'menu')),
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price DECIMAL(10, 2) NOT NULL
        );
        """
    ]
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for sql in sql_commands:
                    cur.execute(sql)
                conn.commit()
                print("All tables created successfully!")
                
    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        sys.exit(1)

def add_sample_data():
    """Add sample data for testing"""
    print("Adding sample data...")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if services table is empty
                cur.execute("SELECT COUNT(*) as count FROM services")
                if cur.fetchone()['count'] == 0:
                    # Add sample services
                    sample_services = [
                        ("Haircut", "haircut.jpg", 500.00, 20.00, 400.00, "Professional haircut and styling"),
                        ("Facial", "facial.jpg", 800.00, 15.00, 680.00, "Relaxing facial treatment"),
                        ("Manicure", "manicure.jpg", 300.00, 10.00, 270.00, "Hand care and nail treatment"),
                        ("Massage", "massage.jpg", 1000.00, 25.00, 750.00, "Full body therapeutic massage"),
                    ]
                    
                    for service in sample_services:
                        cur.execute(
                            """
                            INSERT INTO services (name, photo, price, discount, final_price, description)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            service
                        )
                    print("Sample services added!")
                
                # Check if menu table is empty
                cur.execute("SELECT COUNT(*) as count FROM menu")
                if cur.fetchone()['count'] == 0:
                    # Add sample menu items
                    sample_menu = [
                        ("Margherita Pizza", "pizza.jpg", 350.00, 10.00, 315.00, "Classic cheese and tomato pizza"),
                        ("Burger & Fries", "burger.jpg", 250.00, 15.00, 212.50, "Beef burger with crispy fries"),
                        ("Pasta Alfredo", "pasta.jpg", 280.00, 5.00, 266.00, "Creamy pasta with mushrooms"),
                        ("Fresh Salad", "salad.jpg", 180.00, 0.00, 180.00, "Fresh garden salad with dressing"),
                        ("Chocolate Cake", "cake.jpg", 150.00, 20.00, 120.00, "Rich chocolate cake slice"),
                    ]
                    
                    for item in sample_menu:
                        cur.execute(
                            """
                            INSERT INTO menu (name, photo, price, discount, final_price, description)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            item
                        )
                    print("Sample menu items added!")
                
                conn.commit()
                print("Sample data added successfully!")
                
    except Exception as e:
        print(f"Error adding sample data: {str(e)}")

if __name__ == '__main__':
    create_tables()
    add_sample_data()
    print("Database initialization complete!")