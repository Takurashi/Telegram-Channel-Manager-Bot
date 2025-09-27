from config.settings import ADMIN_IDS
from database.models import User, SessionLocal


def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True

    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == user_id).first()
    db.close()

    return user and user.is_admin


def add_admin(user_id: int) -> bool:
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if user:
        user.is_admin = True
        db.commit()
        db.close()
        return True
    db.close()
    return False


def remove_admin(user_id: int) -> bool:
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if user:
        user.is_admin = False
        db.commit()
        db.close()
        return True
    db.close()
    return False
