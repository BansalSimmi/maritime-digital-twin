#You are doing DOUBLE HASHING:
from passlib.context import CryptContext
import hashlib

#Step 2 — bcrypt --> pwd_context.hash(sha)
#bcrypt → strong password storage
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#Step 1 — SHA256 --> sha = hashlib.sha256(password.encode())
#SHA → normalize input
def hash_password(password: str):
    sha = hashlib.sha256(password.encode()).hexdigest()
    return pwd_context.hash(sha)

def verify_password(password: str, hashed: str):
    sha = hashlib.sha256(password.encode()).hexdigest()
    return pwd_context.verify(sha, hashed)
