import os
import subprocess
import sqlite3
from pathlib import Path
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet

def get_machine_id():
    if os.name == 'nt':  # Windows
        output = subprocess.check_output('wmic csproduct get UUID', shell=True)
        return output.decode().split('\n')[1].strip()
    elif os.path.exists('/etc/machine-id'):  # Linux/macOS
        return open('/etc/machine-id').read().strip()
    else:  # macOS alternative
        output = subprocess.check_output(['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'])
        for line in output.decode().split("\n"):
            if "IOPlatformUUID" in line:
                return line.split('"')[-2]
    return None


def generate_fernet_key():
    """Generate a valid Fernet key from machine-specific data."""
    machine_id = get_machine_id()
    if not machine_id:
        raise ValueError("Could not determine machine ID")
    
    # Hash the machine ID to create a deterministic 32-byte key
    hashed_id = hashlib.sha256(machine_id.encode()).digest()[:32]  # Take first 32 bytes
    
    # Base64 encode to make it a valid Fernet key
    fernet_key = base64.urlsafe_b64encode(hashed_id)
    
    return fernet_key

class SecretManager:
    def __init__(self, db_path='.agentsdb', cache_dir="~/.agentic", key=None):
        self.cache_dir = Path(cache_dir).expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        db_path = Path(cache_dir).expanduser() / db_path
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS secrets (name TEXT PRIMARY KEY, value TEXT)")
        self.conn.commit()
        self.cipher = Fernet(key)

    def set_secret(self, name, value):
        encrypted_value = self.cipher.encrypt(value.encode()).decode()
        self.cursor.execute("INSERT OR REPLACE INTO secrets (name, value) VALUES (?, ?)", (name, encrypted_value))
        self.conn.commit()

    def get_secret(self, name, default_value: Optional[str]=None):
        self.cursor.execute("SELECT value FROM secrets WHERE name=?", (name,))
        result = self.cursor.fetchone()
        return self.cipher.decrypt(result[0].encode()).decode() if result else default_value

    def list_secrets(self):
        self.cursor.execute("SELECT name FROM secrets")
        return [row[0] for row in self.cursor.fetchall()]

    def delete_secret(self, name):
        self.cursor.execute("DELETE FROM secrets WHERE name=?", (name,))
        self.conn.commit()

agentic_secrets = SecretManager(key=generate_fernet_key())
