import os
from app.extensions import db
from app.models.user import User
from app.models.role import Role
from app.utils.security import hash_password

def init_db():
    """
    Initialize the database with default data if it doesn't exist.
    """
    print("Initializing database data...")
    
    # 1. Initialize Roles
    roles = ['admin', 'user', 'device_manager']
    created_roles = {}
    
    for role_name in roles:
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            print(f"Creating role: {role_name}")
            role = Role(
                name=role_name,
                display_name=role_name.capitalize(),
                description=f"Default {role_name} role"
            )
            db.session.add(role)
            db.session.flush() # flush to get ID
        created_roles[role_name] = role
    
    # 2. Initialize Admin User
    admin_username = os.getenv('DEFAULT_ADMIN_USER', 'admin')
    admin_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'password')
    
    admin = User.query.filter_by(username=admin_username).first()
    if not admin:
        print(f"Creating admin user: {admin_username}")
        admin = User(
            username=admin_username,
            email=f"{admin_username}@example.com",
            password_hash=hash_password(admin_password),
            full_name="System Administrator",
            is_active=True,
            primary_role='admin'
        )
        # Assign admin role
        if 'admin' in created_roles:
            admin.roles.append(created_roles['admin'])
            
        db.session.add(admin)
    else:
        print(f"Admin user {admin_username} already exists.")

    try:
        db.session.commit()
        print("Database initialization completed successfully.")
    except Exception as e:
        db.session.rollback()
        print(f"Error initializing database: {e}")
