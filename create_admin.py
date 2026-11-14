
from getpass import getpass

from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.user import User

# Ensure database tables exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    print("=== EventSphere Admin Setup ===")

    full_name = input("Admin full name: ").strip()
    email = input("Admin email: ").strip().lower()
    password = getpass("Admin password (minimum 8 characters): ")

    if len(full_name) < 2:
        raise ValueError("Name must contain at least 2 characters.")

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")

    existing_user = db.query(User).filter(
        User.email == email
    ).first()

    if existing_user:
        raise ValueError("This email is already registered.")

    admin = User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        role="admin",
        is_active=True
    )

    db.add(admin)
    db.commit()

    print("Admin account created successfully.")

except Exception as error:
    db.rollback()
    print("Error:", error)

finally:
    db.close()
