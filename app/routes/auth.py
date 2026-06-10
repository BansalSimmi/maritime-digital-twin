# routes/auth.py --> login / logout / session APIs
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import models, auth, schemas
from app.security import SESSION_COOKIE_NAME, create_session_token
from app.dependencies import get_current_user, get_db

router = APIRouter(prefix="/auth", tags=["🔑 Authentication"])


@router.post("/login")
def login(
    req: schemas.UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.query(models.Account).filter(models.Account.email == req.email).first()

    if not user or not auth.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_session_token(
        {
            "account_id": user.account_id,
            "email": user.email,
            "role": user.role,
        }
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
    )

    # Backwards-compat: clear the old cookie if present.
    response.delete_cookie("user_email")

    return {"message": "Login successful", "role": user.role}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie("user_email")
    return {"message": "Logged out"}


@router.get("/me", response_model=schemas.UserResponse)
def me(current_user=Depends(get_current_user)):
    return current_user
