import pymysql
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def migrate_database():
    """Add missing columns to existing database"""
    
    conn = pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        db=os.getenv('DB_NAME'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cur:
            # Check if email column exists
            cur.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME = 'email'
            """, (os.getenv('DB_NAME'),))
            
            if not cur.fetchone():
                print("Adding email column to users table...")
                cur.execute("""
                    ALTER TABLE users 
                    ADD COLUMN email VARCHAR(255) DEFAULT '' AFTER username
                """)
                print("✓ Email column added")
            else:
                print("✓ Email column already exists")
            
            # Check for created_at in users
            cur.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'users' 
                AND COLUMN_NAME = 'created_at'
            """, (os.getenv('DB_NAME'),))
            
            if not cur.fetchone():
                print("Adding timestamps to users table...")
                cur.execute("""
                    ALTER TABLE users 
                    ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ADD COLUMN last_login TIMESTAMP NULL
                """)
                print("✓ Timestamps added to users table")
            
            # Check for created_at in entries
            cur.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'entries' 
                AND COLUMN_NAME = 'created_at'
            """, (os.getenv('DB_NAME'),))
            
            if not cur.fetchone():
                print("Adding timestamps to entries table...")
                cur.execute("""
                    ALTER TABLE entries 
                    ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                """)
                print("✓ Timestamps added to entries table")
            
            # Add index if it doesn't exist
            cur.execute("""
                SELECT INDEX_NAME 
                FROM INFORMATION_SCHEMA.STATISTICS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'entries' 
                AND INDEX_NAME = 'idx_user_created'
            """, (os.getenv('DB_NAME'),))
            
            if not cur.fetchone():
                print("Adding index to entries table...")
                cur.execute("""
                    CREATE INDEX idx_user_created ON entries(user_id, created_at)
                """)
                print("✓ Index added")
            
            conn.commit()
            print("\n✅ Database migration completed successfully!")
            
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting database migration...")
    migrate_database()