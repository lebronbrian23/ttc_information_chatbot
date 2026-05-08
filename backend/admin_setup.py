"""
Admin setup script for initializing TTC Chatbot authentication.

Usage:
    python -c "from backend.admin_setup import setup_admin; setup_admin()"
    
Or set environment variables first:
    export ADMIN_USERNAME=admin
    export ADMIN_EMAIL=admin@ttc-chatbot.local
    export ADMIN_PASSWORD=MySecurePassword123!
    python -c "from backend.admin_setup import setup_admin; setup_admin()"
"""

import os
import sys
from pathlib import Path

# Add repo root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal, init_db
from backend.auth import create_default_admin, setup_default_users
from backend.models import User, UserRole


def setup_admin():
    """
    Set up admin user and default demo users.
    
    Creates:
    - Admin user (with password from ADMIN_PASSWORD env var or default "changeme")
    - Demo user (username: demo, password: demo123)
    - Moderator user (username: moderator, password: mod123)
    
    Idempotent: Won't fail if users already exist.
    """
    print("TTC Chatbot - Admin Setup")
    print("-" * 50)
    
    # Initialize database
    print("Initializing database...")
    try:
        init_db()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
        
        if admin_count > 0:
            print("⚠️  Admin user already exists")
            admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
            print(f"   Username: {admin.username}")
            print(f"   Email: {admin.email}")
        else:
            print("👤 Creating admin user...")
            
            # Get credentials from environment or use defaults
            admin_username = os.getenv("ADMIN_USERNAME", "admin")
            admin_email = os.getenv("ADMIN_EMAIL", "admin@ttc-chatbot.local")
            admin_password = os.getenv("ADMIN_PASSWORD", "changeme")
            
            # Validate password
            if len(admin_password) < 8:
                print(f"❌ Password too short (min 8 characters)")
                return False
            
            # Create admin
            admin = create_default_admin(admin_username, admin_email, admin_password, db)
            print(f"✅ Admin user created")
            print(f"   Username: {admin.username}")
            print(f"   Email: {admin.email}")
            print(f"   Role: {admin.role.value}")
        
        # Set up default demo users
        print("👥 Setting up demo users...")
        setup_default_users(db)
        
        # List all users
        print("\n📋 Current users:")
        users = db.query(User).all()
        for user in users:
            status = "✓" if user.is_active else "✗"
            print(f"   {status} {user.username:20} | {user.email:30} | {user.role.value:10}")
        
        print("\n✅ Admin setup completed successfully!")
        print("\n📝 Default Credentials:")
        print("   Admin   | admin               | password: changeme")
        print("   User    | demo                | password: demo123")
        print("   Mod     | moderator           | password: mod123")
        print("\n⚠️  IMPORTANT: Change all default passwords in production!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def reset_admin_password(username: str, new_password: str) -> bool:
    """
    Reset admin password.
    
    Usage:
        from backend.admin_setup import reset_admin_password
        reset_admin_password("admin", "NewPassword123!")
    """
    if len(new_password) < 8:
        print(f"❌ Password too short (min 8 characters)")
        return False
    
    # Initialize database
    init_db()
    db = SessionLocal()
    
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ User '{username}' not found")
            return False
        
        from backend.auth import hash_password
        user.hashed_password = hash_password(new_password)
        db.commit()
        print(f"✅ Password updated for user '{username}'")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()


def list_users() -> bool:
    """List all users in the system."""
    print("📋 TTC Chatbot - Users")
    print("-" * 70)
    
    # Initialize database
    init_db()
    db = SessionLocal()
    
    try:
        users = db.query(User).all()
        if not users:
            print("No users found")
            return True
        
        print(f"{'Username':<20} {'Email':<30} {'Role':<10} {'Active':<8}")
        print("-" * 70)
        for user in users:
            active = "✓" if user.is_active else "✗"
            print(f"{user.username:<20} {user.email:<30} {user.role.value:<10} {active:<8}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    """
    Command-line interface for admin setup.
    
    Usage:
        python backend/admin_setup.py              # Setup admin
        python backend/admin_setup.py list         # List users
        python backend/admin_setup.py reset admin  # Reset admin password (prompted)
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="TTC Chatbot Admin Setup Tool",
        epilog="""
Examples:
  python backend/admin_setup.py                    # Initialize admin
  python backend/admin_setup.py list              # List all users
  python backend/admin_setup.py reset admin NewPassword123!  # Reset password
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Setup command (default)
    setup_parser = subparsers.add_parser("setup", help="Setup admin user (default)")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all users")
    
    # Reset command
    reset_parser = subparsers.add_parser("reset", help="Reset user password")
    reset_parser.add_argument("username", help="Username to reset")
    reset_parser.add_argument("password", help="New password")
    
    args = parser.parse_args()
    
    success = False
    if args.command == "list":
        success = list_users()
    elif args.command == "reset":
        success = reset_admin_password(args.username, args.password)
    else:
        success = setup_admin()
    
    sys.exit(0 if success else 1)
