import os
import hmac
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app import app # importing 'app' to get config keys
from pyope.ope import OPE


# i am loading keys from config
try:
    AES_KEY = app.config['ENCRYPTION_KEY']
    HMAC_KEY = app.config['HMAC_KEY']
    OPE_KEY = app.config['OPE_KEY']
except KeyError:
    raise RuntimeError("ENCRYPTION_KEY or HMAC_KEY not set in config.py")

# Confidentiality (AES-GCM)

def encrypt_field(data):
    """
    Encrypts a single piece of data (like age or gender).
    Returns: (ciphertext, nonce) as bytes.
    """
    # Converting data to bytes. str() handles int, bool, etc.
    plaintext = str(data).encode('utf-8')
    
    # getting the AES-GCM cipher object
    aesgcm = AESGCM(AES_KEY)
    
    # generating a unique 12-byte nonce
    nonce = os.urandom(12)
    
    # encrypting
    ciphertext = aesgcm.encrypt(nonce, plaintext, None) # 'None' is is for noassociated data
    
    return ciphertext, nonce

def decrypt_field(ciphertext, nonce, original_type):
    """
    Decrypts a single piece of data and casts it back to its original type.
    """
    try:
        aesgcm = AESGCM(AES_KEY)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        
        # decoding from bytes back to string
        plaintext_str = plaintext_bytes.decode('utf-8')
        
        # cast back to the original type (eg., int, bool)
        if original_type == bool:
            # this converts 'True' -> True, 'False' -> False
            return plaintext_str.lower() == 'true'
        
        return original_type(plaintext_str)
        
    except Exception as e:
        # decryption failed. this might be due to a bad key or tampered data.
        print(f"DECRYPTION FAILED: {e}")
        return None

OPE_PRECISION = 100
ope_cipher = None

try:
    # Initialize the OPE cipher
    ope_cipher = OPE(app.config['OPE_KEY'])
except KeyError:
     raise RuntimeError("OPE_KEY not set in config.py")

def ope_encrypt(data_float):
    if not ope_cipher: return None
    """
    Encrypts a float using OPE by first converting it to a precision integer.
    """
    try:
        # convert float (eg., 68.5) to int (eg., 6850)
        # data_int = int(data_float * OPE_PRECISION)
        data_int = int(round(data_float * OPE_PRECISION))
        
        # encrypt the integer
        return ope_cipher.encrypt(data_int)
    except Exception as e:
        print(f"OPE Encryption Error: {e}")
        return None

def ope_decrypt(data_ciphertext):
    """
    Decrypts an OPE-encrypted integer back to a float.
    """
    try:
        # decrypt the large integer
        data_int = ope_cipher.decrypt(data_ciphertext)
        
        # convert int (eg., 6850) back to float (eg., 68.5)
        return float(data_int) / OPE_PRECISION
    except Exception as e:
        print(f"OPE Decryption Error: {e}")
        return None

# Integrity (HMAC-SHA256) 

def _get_row_string(first, last, gender, age, weight, height, history):
    """
    (Private) Creates the standardized string representation of a row.
    The order MUST always be the same. All inputs are *plaintext*.
    """
    return f"{first}|{last}|{gender}|{age}|{weight}|{height}|{history}"

def generate_row_mac(first, last, gender, age, weight, height, history):
    """
    Generates a new HMAC (tamper-proof seal) for a row of data.
    """
    # getting the standard string for the row
    row_string = _get_row_string(first, last, gender, age, weight, height, history)
    
    # creating the HMAC-SHA256
    mac = hmac.new(
        HMAC_KEY,
        msg=row_string.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest() # this .digest() returns bytes
    
    return mac

def verify_row_mac(first, last, gender, age, weight, height, history, mac_to_check):
    """
    Verifies if a received HMAC is valid for a row of data.
    Returns: True or False
    """
    # Re-generate the HMAC from the plaintext data we have
    calculated_mac = generate_row_mac(first, last, gender, age, weight, height, history)
    
    # comparing the two MACs securely.
    # hmac.compare_digest prevents timing attacks.
    return hmac.compare_digest(calculated_mac, mac_to_check)

# This is starting point for the chain
# it is just 32 empty bytes for SHA-256
GENESIS_HASH = b'\x00' * 32

def generate_chain_hash(current_data_hash, previous_chain_hash):
    """
    Creates the next link in the hash chain.
    
    Args:
        current_data_hash (bytes): The row_mac of the current row.
        previous_chain_hash (bytes): The chain_hash of the previous row.
    """
    # concatenating the two hashes
    combined_hash = current_data_hash + previous_chain_hash
    
    # hashing the result to create the new chain link
    new_chain_hash = hashlib.sha256(combined_hash).digest()
    
    return new_chain_hash