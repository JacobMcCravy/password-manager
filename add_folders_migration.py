import pymysql
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def add_folders_feature():
    """Add folders/categories feature to the database"""
    
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
            # Create folders table
            print("Creating folders table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    color VARCHAR(7) DEFAULT '#3B82F6',
                    icon VARCHAR(50) DEFAULT 'folder',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_folder_name (user_id, name)
                )
            """)
            print("✓ Folders table created")
            
            # Add folder_id to entries table
            cur.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'entries' 
                AND COLUMN_NAME = 'folder_id'
            """, (os.getenv('DB_NAME'),))
            
            if not cur.fetchone():
                print("Adding folder_id to entries table...")
                cur.execute("""
                    ALTER TABLE entries 
                    ADD COLUMN folder_id INT DEFAULT NULL,
                    ADD CONSTRAINT fk_folder 
                    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
                """)
                print("✓ folder_id column added to entries")
            
            # Create default folders for existing users
            print("Creating default folders for existing users...")
            cur.execute("SELECT DISTINCT user_id FROM entries")
            users = cur.fetchall()
            
            for user in users:
                # Check if user already has folders
                cur.execute("SELECT COUNT(*) as count FROM folders WHERE user_id = %s", (user['user_id'],))
                if cur.fetchone()['count'] == 0:
                    # Create default folders
                    cur.execute("""
                        INSERT INTO folders (user_id, name, color, icon) VALUES
                        (%s, 'Personal', '#10b981', 'user'),
                        (%s, 'Work', '#3b82f6', 'briefcase'),
                        (%s, 'Financial', '#f59e0b', 'credit-card'),
                        (%s, 'Social Media', '#8b5cf6', 'share-2')
                    """, (user['user_id'], user['user_id'], user['user_id'], user['user_id']))
            
            conn.commit()
            print("\n✅ Folders feature added successfully!")
            print("\nNote: Existing entries are not assigned to any folder.")
            print("Users can organize them after logging in.")
            
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("Adding folders feature to LockBox...")
    add_folders_feature()