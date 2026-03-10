from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64
import os
import zipfile


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a secure key using PBKDF2HMAC."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = kdf.derive(password.encode())
    return base64.urlsafe_b64encode(key)


def encrypt_data(data: bytes, password: str) -> bytes:
    """Encrypt raw data with AES-256."""
    salt = os.urandom(16)
    key = derive_key(password, salt)
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data)
    return salt + encrypted


def decrypt_data(encrypted_data: bytes, password: str) -> bytes:
    """Decrypt raw data."""
    salt = encrypted_data[:16]
    encrypted = encrypted_data[16:]
    key = derive_key(password, salt)
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
        salt = encrypted_data[:16]
        encrypted = encrypted_data[16:]
        key = derive_key(password, salt)
        fernet = Fernet(key)
        fernet.decrypt(encrypted)
        return True, "File is valid and password is correct"
    except InvalidToken:
        return False, "Invalid password or file is corrupted"
    except Exception as e:
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
