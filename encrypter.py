from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from argon2.low_level import hash_secret_raw, Type as Argon2Type
import base64
import os
import zipfile

# v2 format constants
MAGIC = b"DBRK"
FORMAT_VERSION = 0x02
SALT_SIZE = 32
NONCE_SIZE = 12

# Argon2id parameters (OWASP recommended minimum)
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536  # 64 MiB
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32


def _derive_key_v1(password: str, salt: bytes) -> bytes:
    """Derive a key using PBKDF2HMAC (legacy v1 format)."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = kdf.derive(password.encode())
    return base64.urlsafe_b64encode(key)


def _derive_key_v2(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key using Argon2id."""
    return hash_secret_raw(
        secret=password.encode(),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_HASH_LEN,
        type=Argon2Type.ID,
    )


def _is_v2(data: bytes) -> bool:
    """Check if encrypted data uses the v2 format."""
    return len(data) >= 5 and data[:4] == MAGIC and data[4] == FORMAT_VERSION


def encrypt_data(data: bytes, password: str) -> bytes:
    """Encrypt raw data with AES-256-GCM + Argon2id (v2 format)."""
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key_v2(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    # Format: MAGIC + VERSION + salt + nonce + ciphertext (includes 16-byte GCM tag)
    return MAGIC + bytes([FORMAT_VERSION]) + salt + nonce + ciphertext


def decrypt_data(encrypted_data: bytes, password: str) -> bytes:
    """Decrypt raw data. Auto-detects v2 (AES-256-GCM) or v1 (Fernet) format."""
    if _is_v2(encrypted_data):
        salt = encrypted_data[5:5 + SALT_SIZE]
        nonce = encrypted_data[5 + SALT_SIZE:5 + SALT_SIZE + NONCE_SIZE]
        ciphertext = encrypted_data[5 + SALT_SIZE + NONCE_SIZE:]
        key = _derive_key_v2(password, salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    else:
        # v1 legacy fallback (Fernet + PBKDF2)
        salt = encrypted_data[:16]
        encrypted = encrypted_data[16:]
        key = _derive_key_v1(password, salt)
        fernet = Fernet(key)
        return fernet.decrypt(encrypted)


def verify_file(file_path, password):
    """Verify a .locked file's integrity without writing output.
    Returns (True, message) on success or (False, message) on failure."""
    if not os.path.isfile(file_path):
        return False, "File not found"
    if not file_path.endswith(".locked"):
        return False, "Not a .locked file"
    try:
        with open(file_path, "rb") as f:
            encrypted_data = f.read()
        if _is_v2(encrypted_data):
            salt = encrypted_data[5:5 + SALT_SIZE]
            nonce = encrypted_data[5 + SALT_SIZE:5 + SALT_SIZE + NONCE_SIZE]
            ciphertext = encrypted_data[5 + SALT_SIZE + NONCE_SIZE:]
            key = _derive_key_v2(password, salt)
            aesgcm = AESGCM(key)
            aesgcm.decrypt(nonce, ciphertext, None)
        else:
            salt = encrypted_data[:16]
            encrypted = encrypted_data[16:]
            key = _derive_key_v1(password, salt)
            fernet = Fernet(key)
            fernet.decrypt(encrypted)
        return True, "File is valid and password is correct"
    except (InvalidToken, Exception) as e:
        if isinstance(e, InvalidToken):
            return False, "Invalid password or file is corrupted"
        return False, f"Verification failed: {e}"


def secure_delete(path, passes=3):
    """Securely delete a file by overwriting with random data multiple times."""
    if not os.path.isfile(path):
        return
    size = os.path.getsize(path)
    with open(path, "r+b") as f:
        for _ in range(passes):
            f.seek(0)
            f.write(os.urandom(size))
            f.flush()
            os.fsync(f.fileno())
    os.remove(path)


def secure_delete_folder(folder_path, passes=3):
    """Securely delete all files in a folder, then remove the directory tree."""
    for root, dirs, files in os.walk(folder_path, topdown=False):
        for name in files:
            secure_delete(os.path.join(root, name), passes)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(folder_path)


def encrypt_file(file_path, password, progress_callback=None, do_secure_delete=False):
    """Encrypt a single file."""
    if progress_callback:
        progress_callback(0, f"Reading {os.path.basename(file_path)}...")
    with open(file_path, "rb") as file:
        data = file.read()
    if progress_callback:
        progress_callback(33, "Encrypting...")
    encrypted = encrypt_data(data, password)
    if progress_callback:
        progress_callback(66, "Writing encrypted file...")
    with open(file_path + ".locked", "wb") as file:
        file.write(encrypted)
    if do_secure_delete:
        if progress_callback:
            progress_callback(85, "Securely deleting original...")
        secure_delete(file_path)
    if progress_callback:
        progress_callback(100, "Done")


def decrypt_file(file_path, password, progress_callback=None, do_secure_delete=False):
    """Decrypt a single file."""
    if progress_callback:
        progress_callback(0, f"Reading {os.path.basename(file_path)}...")
    with open(file_path, "rb") as file:
        encrypted = file.read()
    if progress_callback:
        progress_callback(33, "Decrypting...")
    decrypted = decrypt_data(encrypted, password)
    if progress_callback:
        progress_callback(66, "Writing decrypted file...")
    with open(file_path.replace(".locked", ""), "wb") as file:
        file.write(decrypted)
    if do_secure_delete:
        if progress_callback:
            progress_callback(85, "Securely deleting encrypted file...")
        secure_delete(file_path)
    if progress_callback:
        progress_callback(100, "Done")


def encrypt_folder(folder_path, password, progress_callback=None, do_secure_delete=False):
    """Encrypt a folder into a single encrypted archive."""
    if progress_callback:
        progress_callback(0, "Compressing folder...")
    temp_zip = folder_path + "_temp_archive.zip"
    with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        all_files = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                all_files.append(os.path.join(root, file))
        for i, fp in enumerate(all_files):
            arcname = os.path.relpath(fp, folder_path)
            zipf.write(fp, arcname)
            if progress_callback and all_files:
                pct = int((i + 1) / len(all_files) * 40)
                progress_callback(pct, f"Compressing {arcname}...")
    if progress_callback:
        progress_callback(40, "Reading compressed data...")
    with open(temp_zip, "rb") as file:
        data = file.read()
    if progress_callback:
        progress_callback(50, "Encrypting...")
    encrypted = encrypt_data(data, password)
    if progress_callback:
        progress_callback(80, "Writing encrypted archive...")
    with open(folder_path + ".locked", "wb") as file:
        file.write(encrypted)
    os.remove(temp_zip)
    if do_secure_delete:
        if progress_callback:
            progress_callback(90, "Securely deleting original folder...")
        secure_delete_folder(folder_path)
    if progress_callback:
        progress_callback(100, "Done")


def decrypt_folder(file_path, password, progress_callback=None, do_secure_delete=False):
    """Decrypt an encrypted folder archive."""
    if progress_callback:
        progress_callback(0, "Reading encrypted archive...")
    with open(file_path, "rb") as file:
        encrypted = file.read()
    if progress_callback:
        progress_callback(20, "Decrypting...")
    decrypted = decrypt_data(encrypted, password)
    temp_zip = file_path.replace(".locked", "") + "_temp_archive.zip"
    if progress_callback:
        progress_callback(60, "Writing temporary archive...")
    with open(temp_zip, "wb") as file:
        file.write(decrypted)
    output_folder = file_path.replace(".locked", "")
    if progress_callback:
        progress_callback(70, "Extracting files...")
    with zipfile.ZipFile(temp_zip, "r") as zipf:
        zipf.extractall(output_folder)
    os.remove(temp_zip)
    if do_secure_delete:
        if progress_callback:
            progress_callback(90, "Securely deleting encrypted archive...")
        secure_delete(file_path)
    if progress_callback:
        progress_callback(100, "Done")
