# migrate_profile_pics.py
import os
import sys
import psycopg
from psycopg.rows import dict_row
import cloudinary
import cloudinary.uploader
from PIL import Image
import io

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    return psycopg.connect(database_url, row_factory=dict_row)

def migrate_existing_users():
    """Migrate existing users' profile pics to Cloudinary"""
    print("Starting migration of existing profile pictures...")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get all users with local profile pics
        cur.execute("""
            SELECT id, profile_pic 
            FROM users 
            WHERE profile_pic NOT LIKE 'http%' 
            AND profile_pic != 'default-avatar.jpg'
        """)
        
        users = cur.fetchall()
        print(f"Found {len(users)} users with local profile pictures")
        
        migrated_count = 0
        failed_count = 0
        
        for user in users:
            user_id = user['id']
            old_pic = user['profile_pic']
            
            # Check if file exists locally
            filepath = os.path.join('static', 'uploads', old_pic)
            
            if os.path.exists(filepath):
                try:
                    # Upload to Cloudinary
                    with open(filepath, 'rb') as f:
                        result = cloudinary.uploader.upload(
                            f,
                            folder="profile_pics",
                            public_id=f"user_migrated_{user_id}",
                            overwrite=True,
                            transformation=[
                                {'width': 500, 'height': 500, 'crop': 'fill'},
                                {'quality': 'auto'}
                            ]
                        )
                    
                    # Update database with Cloudinary URL
                    cur.execute(
                        "UPDATE users SET profile_pic = %s WHERE id = %s",
                        (result["secure_url"], user_id)
                    )
                    
                    # Delete local file (optional)
                    # os.remove(filepath)
                    
                    print(f"✓ Migrated user {user_id}: {old_pic} → Cloudinary")
                    migrated_count += 1
                    
                except Exception as e:
                    print(f"✗ Failed to migrate user {user_id}: {str(e)}")
                    failed_count += 1
            else:
                # File doesn't exist, set to default
                cur.execute(
                    "UPDATE users SET profile_pic = %s WHERE id = %s",
                    ("https://res.cloudinary.com/demo/image/upload/v1234567890/profile_pics/default-avatar.png", user_id)
                )
                print(f"⚠ File not found for user {user_id}, set to default")
        
        conn.commit()
        conn.close()
        
        print("\n" + "="*50)
        print(f"MIGRATION SUMMARY:")
        print(f"Total users processed: {len(users)}")
        print(f"Successfully migrated: {migrated_count}")
        print(f"Failed: {failed_count}")
        print(f"Skipped (file not found): {len(users) - migrated_count - failed_count}")
        print("="*50)
        
    except Exception as e:
        print(f"Migration error: {str(e)}")

if __name__ == '__main__':
    # Set environment variables if running locally
    if not os.environ.get('DATABASE_URL'):
        print("Please set DATABASE_URL environment variable")
        print("Example: export DATABASE_URL=postgresql://user:pass@localhost/dbname")
        sys.exit(1)
    
    migrate_existing_users()