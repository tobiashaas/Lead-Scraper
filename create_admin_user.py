"""
Create Admin User
Erstellt einen Admin-User für die Anwendung
"""

from app.database.database import SessionLocal
from app.database.models import User, UserRole
from app.core.security import get_password_hash


def create_admin():
    """Erstellt Admin-User"""
    db = SessionLocal()

    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(User.username == "admin").first()
        if existing_admin:
            print("⚠️  Admin user already exists")
            return

        # Create admin user
        admin = User(
            username="admin",
            email="admin@kr-leads.de",
            full_name="System Administrator",
            hashed_password=get_password_hash("admin123"),  # Change in production!
            role=UserRole.ADMIN,
            is_superuser=True,
            is_active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("✅ Admin user created successfully!")
        print(f"   Username: {admin.username}")
        print(f"   Email: {admin.email}")
        print(f"   Password: admin123 (CHANGE THIS!)")
        print(f"   Role: {admin.role.value}")

    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Create Admin User")
    print("=" * 60)
    print()
    create_admin()
