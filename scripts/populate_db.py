import sys
import os
import mysql.connector

# adds the root folder of the project to the 
# list of places Python looks for code.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from app.database import get_db_connection
from app import app, database, crypto

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    user_group ENUM('H', 'R') NOT NULL
)
"""

CREATE_PATIENTS_TABLE = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    gender VARBINARY(255),
    gender_nonce VARBINARY(12),
    age VARBINARY(255),
    age_nonce VARBINARY(12),
    weight BIGINT,
    height FLOAT,
    health_history TEXT,
    row_mac VARBINARY(32),
    chain_hash VARBINARY(32)
)
"""
# SQL query to insert a new patient
INSERT_PATIENT_QUERY = """
INSERT INTO patients (
    first_name, last_name, 
    gender, gender_nonce,
    age, age_nonce,
    weight, height, health_history,
    row_mac,
    chain_hash
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def setup_database():
    cnx = None
    cursor = None
    try:
        print("Connecting to Aiven database...")
        cnx = get_db_connection()
        if not cnx:
            print("Connection failed. Check your config.py and certs/ca.pem file.")
            return

        cursor = cnx.cursor()
        print("Connection successful.")

        # Create Tables
        print("Creating 'users' table (if not exists)...")
        cursor.execute(CREATE_USERS_TABLE)
        print("Creating 'patients' table (if not exists)...")
        cursor.execute(CREATE_PATIENTS_TABLE)
        print("Tables created successfully.")

        # CLEAR OLD DATA
        print("Clearing all old data from 'patients' table...")
        cursor.execute("TRUNCATE TABLE patients")
        print("Old data cleared.")

        print("Loading imported patient data from patients_import...")
        cursor.execute("""
            SELECT first_name, last_name, gender, age, weight, height, health_history
            FROM patients_import
            ORDER BY patient_id ASC
        """)
        imported_rows = cursor.fetchall()
        print(f"Loaded {len(imported_rows)} rows from patients_import.")      
 
        # Populating with our custom, encrypted data
        print(f"Populating 'patients' table with {len(imported_rows)}, all chained custom encrypted records...")
        
        print(f"Encrypting and inserting {len(imported_rows)} imported rows...")

        # initializing chain with Genesis Hash
        last_known_hash = crypto.GENESIS_HASH
        
        # Loop over custom list
        for row_data in imported_rows:
            # Get the 7 plaintext fields from the tuple
            first_name, last_name, gender, age, weight, height, health_history = row_data

            if gender is None:
                gender_bool = None
            else:
                gender_bool = bool(gender) # Converts 1/0 to True/False
            
            # We MUST round before encrypting to avoid floating point mismatches
            if weight is not None:
                weight = round(float(weight), 2)

            if height is not None:
                height = round(float(height), 2)

            gender_ct, gender_nonce = crypto.encrypt_field(gender_bool) # Use gender_bool!
            age_ct, age_nonce = crypto.encrypt_field(age)
            
            # Encrypt Weight
            encrypted_weight = crypto.ope_encrypt(weight) if weight is not None else None
            
            # generating the integrity seal using the CORRECT boolean and rounded weight/height
            row_mac = crypto.generate_row_mac(
                first_name, last_name, gender_bool, age, weight, height, health_history
            )

            # generating the chain hash
            new_chain_hash = crypto.generate_chain_hash(row_mac, last_known_hash)

            # building the 10-value tuple for the SQL query
            patient_data_tuple = (
                first_name, last_name,
                gender_ct, gender_nonce,
                age_ct, age_nonce,
                encrypted_weight, height, health_history,
                row_mac,
                new_chain_hash
            )
            
            cursor.execute(INSERT_PATIENT_QUERY, patient_data_tuple)

            # updating hash for next loop
            last_known_hash = new_chain_hash

        cnx.commit()
        
        print("\n Database Setup Complete! --->")
        print(f"{len(imported_rows)} custom, chained records added to 'patients'.")
    
    except mysql.connector.Error as err:
        print(f"\nAn Error Occurred --->")
        print(f"Error: {err}")
        if cnx:
            print("Rolling back changes...")
            cnx.rollback()
    finally:
        if cursor: cursor.close()
        if cnx: cnx.close()
        print("Database connection closed.")

if __name__ == "__main__":
    with app.app_context():
        setup_database()