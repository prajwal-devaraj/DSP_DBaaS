from flask import request, jsonify, redirect, url_for
from app import app, bcrypt 
from . import database, auth
from . import crypto
import mysql.connector
import jwt
import datetime
import hmac

@app.route('/')
def index():
    return jsonify({"message": "Welcome to the Secure Database API. Please /register or /login."})

# Endpoint: user Registration
@app.route('/register', methods=['POST'])
def register_user():
    data = request.json
    try:
        username = data['username']
        password = data['password']
        occupation = data['occupation']
    except KeyError:
        return jsonify({"error": "Missing 'username', 'password', or 'occupation'"}), 400

    group = None
    normalized_occupation = occupation.lower().strip()
    
    if normalized_occupation in ['doctor', 'nurse', 'admin', 'hospital administration staff']:
        group = 'H'
    elif normalized_occupation == 'researcher':
        group = 'R'
    
    if group is None:
        return jsonify({
            "error": f"Invalid occupation: '{occupation}'. Must be Doctor, Nurse, Admin, or Researcher."
        }), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    cnx = None
    cursor = None
    try:
        cnx = database.get_db_connection()
        if not cnx: return jsonify({"error": "Database connection failed"}), 500
        
        cursor = cnx.cursor()
        query = "INSERT INTO users (username, password_hash, user_group) VALUES (%s, %s, %s)"
        cursor.execute(query, (username, hashed_password, group))
        cnx.commit()
        
        return jsonify({"message": "User registered successfully"}), 201
        
    except mysql.connector.Error as err:
        if err.errno == 1062:
             return jsonify({"error": "Username already exists"}), 409
        return jsonify({"error": f"Database error: {err}"}), 500
    finally:
        if cursor: cursor.close()
        if cnx: cnx.close()

# Endpoint: user login
@app.route('/login', methods=['POST'])
def login_user():
    data = request.json
    try:
        username = data['username']
        password = data['password']
    except KeyError:
        return jsonify({"error": "Missing 'username' or 'password'"}), 400

    cnx = None
    cursor = None
    try:
        cnx = database.get_db_connection()
        if not cnx: return jsonify({"error": "Database connection failed"}), 500
            
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user or not bcrypt.check_password_hash(user['password_hash'], password):
            return jsonify({"error": "Invalid username or password"}), 401
            
        token_payload = {
            'user_id': user['user_id'],
            'username': user['username'],
            'group': user['user_group'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }
        token = jwt.encode(token_payload, app.config['JWT_SECRET_KEY'], algorithm="HS256")
        
        return jsonify({"message": "Login successful", "token": token, "group": user['user_group']})

    except mysql.connector.Error as err:
        return jsonify({"error": f"Database error: {err}"}), 500
    finally:
        if cursor: cursor.close()
        if cnx: cnx.close()

#
# Endpoint: Getting All Patient Data (OPE Enabled)
#
@app.route('/query_all', methods=['GET'])
@auth.token_required
def get_all_patients(current_user):
    cnx = None
    cursor = None
    try:
        cnx = database.get_db_connection()
        if not cnx: return jsonify({"error": "Database connection failed"}), 500
            
        cursor = cnx.cursor(dictionary=True)
        cursor.execute("SELECT * FROM patients ORDER BY patient_id ASC")
        results = cursor.fetchall()

        plaintext_results = []
        last_known_hash = crypto.GENESIS_HASH

        for row in results:
            try:
                # 1. Decrypt (Confidentiality)
                decrypted_gender = crypto.decrypt_field(row['gender'], row['gender_nonce'], bool)
                decrypted_age = crypto.decrypt_field(row['age'], row['age_nonce'], int)
                
                raw_weight = crypto.ope_decrypt(row['weight'])
                if raw_weight is not None:
                    decrypted_weight = round(raw_weight, 2)
                else:
                    decrypted_weight = None

                if decrypted_gender is None or decrypted_age is None or decrypted_weight is None:
                    print(f"WARNING: Decryption FAILED for patient_id {row['patient_id']}")
                    continue 

                row_height = row['height']
                if row_height is not None:
                    row_height = round(float(row_height), 2)

                # 2. Verify Integrity
                is_valid = crypto.verify_row_mac(
                    row['first_name'],
                    row['last_name'],
                    decrypted_gender, 
                    decrypted_age,
                    decrypted_weight, 
                    row_height,
                    row['health_history'],
                    row['row_mac']
                )

                if not is_valid:
                    print(f"WARNING: Integrity check FAILED for patient_id {row['patient_id']}")
                    continue
                    
                # 3. Verify Completeness
                current_data_hash = crypto.generate_row_mac(
                    row['first_name'], row['last_name'],
                    decrypted_gender, decrypted_age,
                    decrypted_weight,
                    row_height,
                    row['health_history']
                )
                
                expected_chain_hash = crypto.generate_chain_hash(current_data_hash, last_known_hash)
                
                if not hmac.compare_digest(expected_chain_hash, row['chain_hash']):
                    print(f"FATAL: Query Completeness FAILED! Chain broken at patient_id {row['patient_id']}.")
                    return jsonify({"error": "Query Failed: Data is missing or out of order."}), 500

                last_known_hash = row['chain_hash']

                # 4. Build Plaintext Row
                row['gender'] = decrypted_gender
                row['age'] = decrypted_age
                row['weight'] = decrypted_weight
                row['height'] = row_height
                
                if current_user['user_group'] == 'R':
                    del row['first_name']
                    del row['last_name']

                del row['gender_nonce']
                del row['age_nonce']
                del row['row_mac']
                del row['chain_hash']
                
                plaintext_results.append(row)
                
            except Exception as e:
                print(f"Error processing row {row.get('patient_id')}: {e}")
                continue

        return jsonify(plaintext_results)

    except mysql.connector.Error as err:
        return jsonify({"error": f"Database query failed: {err}"}), 500
    finally:
        if cursor: cursor.close()
        if cnx: cnx.close()

#
# Endpoint: Adding a New Patient (OPE Enabled)
#
@app.route('/add_data', methods=['POST'])
@auth.token_required
def add_patient(current_user):
    if current_user['user_group'] != 'H':
        return jsonify({"error": "Access Denied: Only users from Group H can add new data."}), 403

    data = request.json
    
    INSERT_PATIENT_QUERY = """
    INSERT INTO patients (
        first_name, last_name, 
        gender, gender_nonce,
        age, age_nonce,
        weight, height, health_history,
        row_mac, chain_hash
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    cnx = None
    cursor = None
    try:
        try:
            first_name, last_name, gender, age, weight, height, health_history = (
                data['first_name'], data['last_name'], data['gender'],
                data['age'], data['weight'], data['height'], data['health_history']
            )
            # Rounding BEFORE encryption ensures consistency
            weight = round(float(weight), 2)
            height = round(float(height), 2)
            
        except KeyError:
            return jsonify({"error": "Missing data in request JSON."}), 400
        
        # 1. Encrypt Standard Fields
        gender_ct, gender_nonce = crypto.encrypt_field(gender)
        age_ct, age_nonce = crypto.encrypt_field(age)

        # 2. Encrypt Weight (OPE)
        encrypted_weight = crypto.ope_encrypt(weight)
        if encrypted_weight is None:
             return jsonify({"error": "Encryption failed for weight"}), 500

        # 3. Generate Integrity Seal
        row_mac = crypto.generate_row_mac(
            first_name, last_name, gender, age, weight, height, health_history
        )

        # 4. Get Previous Hash
        cnx = database.get_db_connection()
        if not cnx: return jsonify({"error": "Database connection failed"}), 500
        cursor = cnx.cursor()

        cursor.execute("SELECT chain_hash FROM patients WHERE patient_id = (SELECT MAX(patient_id) FROM patients)")
        result = cursor.fetchone()
        previous_hash = result[0] if result else crypto.GENESIS_HASH
            
        # 5. Generate New Chain Hash
        new_chain_hash = crypto.generate_chain_hash(row_mac, previous_hash)

        # 6. Insert Data
        patient_data_tuple = (
            first_name, last_name,
            gender_ct, gender_nonce,
            age_ct, age_nonce,
            encrypted_weight, 
            height, health_history,
            row_mac, new_chain_hash
        )

        cursor.execute(INSERT_PATIENT_QUERY, patient_data_tuple)
        cnx.commit()
        
        return jsonify({
            "message": "Patient added successfully", 
            "patient_id": cursor.lastrowid
        }), 201

    except mysql.connector.Error as err:
        if cnx: cnx.rollback()
        return jsonify({"error": f"Database insert failed: {err}"}), 500
    finally:
        if cursor: cursor.close()
        if cnx: cnx.close()

#
# Endpoint: Search by Weight (OPE Range Query)
#
@app.route('/query_by_weight', methods=['GET'])
@auth.token_required
def query_by_weight(current_user):
    try:
        min_weight = request.args.get('min', type=float)
        max_weight = request.args.get('max', type=float)
        if min_weight is None or max_weight is None:
            return jsonify({"error": "Missing 'min' or 'max' parameters"}), 400
    except ValueError:
        return jsonify({"error": "Invalid numbers"}), 400

    encrypted_min = crypto.ope_encrypt(min_weight)
    encrypted_max = crypto.ope_encrypt(max_weight)
    
    query = "SELECT * FROM patients WHERE weight BETWEEN %s AND %s ORDER BY patient_id ASC"
    
    cnx = None
    cursor = None
    try:
        cnx = database.get_db_connection()
        if not cnx: return jsonify({"error": "DB failed"}), 500
        cursor = cnx.cursor(dictionary=True)
        cursor.execute(query, (encrypted_min, encrypted_max))
        results = cursor.fetchall()
        
        plaintext_results = []
        for row in results:
            try:
                decrypted_gender = crypto.decrypt_field(row['gender'], row['gender_nonce'], bool)
                decrypted_age = crypto.decrypt_field(row['age'], row['age_nonce'], int)
                
                # --- SAFETY FIX: Check None ---
                raw_weight = crypto.ope_decrypt(row['weight'])
                if raw_weight is not None:
                    decrypted_weight = round(raw_weight, 2)
                else:
                    decrypted_weight = None

                if decrypted_gender is None or decrypted_age is None or decrypted_weight is None:
                    continue

                # --- SAFETY FIX: Check None for height ---
                row_height = row['height']
                if row_height is not None:
                    row_height = round(float(row_height), 2)

                is_valid = crypto.verify_row_mac(
                    row['first_name'], row['last_name'],
                    decrypted_gender, decrypted_age, decrypted_weight,
                    row_height,
                    row['health_history'], row['row_mac']
                )
                if not is_valid: continue

                row['gender'] = decrypted_gender
                row['age'] = decrypted_age
                row['weight'] = decrypted_weight
                row['height'] = row_height

                if current_user['user_group'] == 'R':
                    del row['first_name']
                    del row['last_name']
                
                del row['gender_nonce']
                del row['age_nonce']
                del row['row_mac']
                del row['chain_hash']
                
                plaintext_results.append(row)
            except:
                continue

        return jsonify(plaintext_results)
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 500
    finally:
        if cursor: cursor.close()
        if cnx: cnx.close()