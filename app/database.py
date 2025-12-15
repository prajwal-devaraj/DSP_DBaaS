import mysql.connector
import config 
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_PATH = os.path.join(BASE_DIR, '..', 'certs', 'ca.pem')

db_config = {
    'user': config.DB_USER,
    'password': config.DB_PASSWORD,
    'host': config.DB_HOST,
    'port': config.DB_PORT,        
    'database': config.DB_NAME,
    'ssl_ca': CERT_PATH,         
    'ssl_verify_cert': True
}

def get_db_connection():
    """To Establish and return a new database connection."""
    try:
        cnx = mysql.connector.connect(**db_config)
        return cnx
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None