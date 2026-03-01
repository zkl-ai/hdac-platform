from app.models import User

class AuthService:

    @staticmethod
    def authenticate(username, password):
        user = User.query.filter_by(username=username).first()
        if not user:
            return None, "User not found"

        if not user.check_password(password):
            return None, "Invalid password"

        if not user.is_active:
            return None, "User is inactive"

        return user, None
