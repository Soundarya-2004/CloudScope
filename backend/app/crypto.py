from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Securely extract the secret key, fail loudly if not deployed securely
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is absolutely required for production security!")

cipher_suite = Fernet(SECRET_KEY.encode())

def encrypt(text: str) -> str:
    return cipher_suite.encrypt(text.encode()).decode()

def decrypt(encrypted_text: str) -> str:
    return cipher_suite.decrypt(encrypted_text.encode()).decode()
