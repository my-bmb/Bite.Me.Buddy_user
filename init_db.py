# init_db.py - Initialize database with sample data
import os
import sys
import psycopg
from psycopg.rows import dict_row

def get_db_connection():
    """Establish database connection"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("Error: DATABASE_URL environment variable is not set")
        sys.exit(1)
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    return psycopg.connect(database_url, row_factory=dict_row)

def init_database():
    """Initialize database with schema and sample data"""
    print("Initializing database...")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Read and execute schema
                with open('schema.sql', 'r') as f:
                    schema = f.read()
                
                # Split by semicolon and execute each statement
                statements = schema.split(';')
                for statement in statements:
                    if statement.strip():
                        cur.execute(statement)
                
                # Check if sample data exists
                cur.execute("SELECT COUNT(*) as count FROM services")
                services_count = cur.fetchone()['count']
                
                cur.execute("SELECT COUNT(*) as count FROM menu")
                menu_count = cur.fetchone()['count']
                
                # Insert sample services if table is empty
                if services_count == 0:
                    print("Inserting sample services...")
                    sample_services = [
                        ("Haircut", "haircut.jpg", 500.00, 20.00, 400.00, "Professional haircut and styling", "active"),
                        ("Facial", "facial.jpg", 800.00, 15.00, 680.00, "Relaxing facial treatment", "active"),
                        ("Manicure", "manicure.jpg", 300.00, 10.00, 270.00, "Hand care and nail treatment", "active"),
                        ("Massage", "massage.jpg", 1000.00, 25.00, 750.00, "Full body therapeutic massage", "active"),
                    ]
                    
                    for service in sample_services:
                        cur.execute(
                            """
                            INSERT INTO services (name, photo, price, discount, final_price, description, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            service
                        )
                
                # Insert sample menu items if table is empty
                if menu_count == 0:
                    print("Inserting sample menu items...")
                    sample_menu = [
                        ("Margherita Pizza", "pizza.jpg", 350.00, 10.00, 315.00, "Classic cheese and tomato pizza", "active"),
                        ("Burger & Fries", "burger.jpg", 250.00, 15.00, 212.50, "Beef burger with crispy fries", "active"),
                        ("Pasta Alfredo", "pasta.jpg", 280.00, 5.00, 266.00, "Creamy pasta with mushrooms", "active"),
                        ("Fresh Salad", "salad.jpg", 180.00, 0.00, 180.00, "Fresh garden salad with dressing", "active"),
                        ("Chocolate Cake", "cake.jpg", 150.00, 20.00, 120.00, "Rich chocolate cake slice", "active"),
                    ]
                    
                    for item in sample_menu:
                        cur.execute(
                            """
                            INSERT INTO menu (name, photo, price, discount, final_price, description, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            item
                        )
                
                conn.commit()
                print("Database initialized successfully!")
                
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    init_database()
