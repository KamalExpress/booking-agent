import os
from cryptography.fernet import Fernet

class SecretsManager:
    """
    Manages encryption and decryption of secrets.
    Uses Fernet symmetric encryption.
    """
    def __init__(self):
        self._key = self._load_or_generate_key()
        self.fernet = Fernet(self._key)

    def _load_or_generate_key(self) -> bytes:
        # Check environment first
        key = os.getenv("SECRET_MASTER_KEY")
        if key:
            return key.encode()
            
        # Try loading from data dir if we have a volume, otherwise local .env
        env_file = "data/secrets.env" if os.path.exists("data") else os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                for line in f:
                    if line.startswith("SECRET_MASTER_KEY="):
                        return line.split("=", 1)[1].strip().encode()
        
        # Generate new key and append to .env
        print("WARNING: Generating new SECRET_MASTER_KEY and appending to .env")
        new_key = Fernet.generate_key()
        with open(env_file, "a") as f:
            f.write(f"\nSECRET_MASTER_KEY={new_key.decode()}\n")
            
        return new_key

    def encrypt(self, secret: str) -> str:
        """Encrypt a plaintext string."""
        if not secret:
            return ""
        return self.fernet.encrypt(secret.encode()).decode()

    def decrypt(self, encrypted_secret: str) -> str:
        """Decrypt an encrypted string."""
        if not encrypted_secret:
            return ""
        try:
            return self.fernet.decrypt(encrypted_secret.encode()).decode()
        except Exception as e:
            print(f"Failed to decrypt secret: {e}")
            return ""

# Global instance
secrets_manager = SecretsManager()
