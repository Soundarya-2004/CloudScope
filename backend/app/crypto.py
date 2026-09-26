import os
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Search for .env in current directory, backend/, or workspace root
env_paths = [
    Path.cwd() / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env"
]
for p in env_paths:
    if p.exists():
        load_dotenv(dotenv_path=p)

# Securely extract or generate a safe Fernet key
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    # Use deterministic fallback key for development/tests so execution doesn't crash
    SECRET_KEY = "tIObKkQpUSwX_P4pKYt3rZLC8tZ6JeAUXNKpUtvySRc="

cipher_suite = Fernet(SECRET_KEY.encode())

def encrypt(text: str) -> str:
    if not text:
        return ""
    return cipher_suite.encrypt(text.encode()).decode()

def decrypt(encrypted_text: str) -> str:
    if not encrypted_text:
        return ""
    return cipher_suite.decrypt(encrypted_text.encode()).decode()
