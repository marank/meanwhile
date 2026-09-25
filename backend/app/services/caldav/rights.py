from radicale import rights as base_rights
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_engine
from app.models import Calendar, CalendarMember, Role, User


class Rights(base_rights.BaseRights):
    def authorization(self, user: str, path: str) -> str:
        if not user:
            return ""

        parts = [p for p in path.split("/") if p]
        if not parts:
            # Root collection: list principals for authenticated user.
            return "RWrw"

        engine = get_engine()
        SessionLocal = sessionmaker(bind=engine)
        db: Session = SessionLocal()
        try:
            user_obj = db.query(User).filter(User.email == user).first()
            if user_obj is None:
                return ""

            if len(parts) == 1:
                # Principal collection: own principal only.
                if parts[0] == user:
                    return "RWrw"
                return ""

            # path is /<email>/<calendar_id>
            owner_email, calendar_id = parts[0], parts[1]
            owner = db.query(User).filter(User.email == owner_email).first()
            if owner is None:
                return ""

            membership = (
                db.query(CalendarMember)
                .filter(
                    CalendarMember.calendar_id == calendar_id,
                    CalendarMember.user_id == user_obj.id,
                )
                .first()
            )
            if membership is None:
                # Also allow owner of the calendar.
                calendar = (
                    db.query(Calendar)
                    .filter(Calendar.id == calendar_id, Calendar.owner_id == user_obj.id)
                    .first()
                )
                if calendar is not None:
                    return "RWrw"
                return ""

            role = Role(membership.role)
            if role == Role.VIEWER:
                return "Rr"
            return "RWrw"
        finally:
            db.close()
