from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models
from app.security import SESSION_COOKIE_NAME, verify_session_token


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        payload = verify_session_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid session")

        account_id = payload.get("account_id")
        email = payload.get("email")

        q = db.query(models.Account)
        if account_id is not None:
            user = q.filter(models.Account.account_id == int(account_id)).first()
        elif email:
            user = q.filter(models.Account.email == email).first()
        else:
            user = None

        if not user:
            raise HTTPException(status_code=401, detail="Invalid session")

        return user

    # Backwards-compat: unsigned cookie (legacy)
    email = request.cookies.get("user_email")

    if not email:
        raise HTTPException(401, "Not logged in")

    user = db.query(models.Account)\
        .filter(models.Account.email == email)\
        .first()

    if not user:
        raise HTTPException(401, "Invalid session")

    return user


def admin_only(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin only")

    return current_user


