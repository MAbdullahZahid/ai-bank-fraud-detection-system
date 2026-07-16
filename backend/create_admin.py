"""
Run this ONCE after the schema is created, to create your first admin login.
Usage: python create_admin.py
"""

from app.database import SessionLocal, init_db
from app.models.admin import Admin
from app.services.auth_service import hash_password

init_db()  # ensures tables exist before inserting

db = SessionLocal()

username = input("Choose admin username: ")
password = input("Choose admin password: ")

existing = db.query(Admin).filter(Admin.username == username).first()
if existing:
    print(f"Admin '{username}' already exists.")
else:
    admin = Admin(username=username, password=hash_password(password))
    db.add(admin)
    db.commit()
    print(f"Admin '{username}' created successfully.")

db.close()
