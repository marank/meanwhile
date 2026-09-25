from radicale import auth as base_auth
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import verify_password
from app.database import get_engine
from app.models import AppPassword, User


class Auth(base_auth.BaseAuth):
    def _login_ext(self, login: str, password: str, context) -> str:
        engine = get_engine()
        SessionLocal = sessionmaker(bind=engine)
        db: Session = SessionLocal()
        try:
            user = db.query(User).filter(User.email == login).first()
            if user is None:
                return ""

            app_passwords = (
                db.query(AppPassword)
                .filter(AppPassword.user_id == user.id)
                .all()
            )
            if app_passwords:
                for app_password in app_passwords:
                    if verify_password(password, app_password.password_hash):
                        return login
                return ""

            if verify_password(password, user.hashed_password):
                return login
            return ""
        finally:
            db.close()
