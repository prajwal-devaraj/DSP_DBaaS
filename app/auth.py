import jwt
from functools import wraps
from flask import request, jsonify
from app import app, database

def token_required(f):
    """
    A decorator function to validate JWT tokens and pass user info to the route.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # now checking if 'Authorization' header is present in the request
        if 'Authorization' in request.headers:
            # the header format here is "Bearer <token>"
            # we split by space and take the 2nd part ie the token
            try:
                token = request.headers['Authorization'].split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Invalid Token format. Use "Bearer <token>".'}), 401

        if not token:
            return jsonify({'message': 'Authentication token is missing!'}), 401

        try:
            # decoding the token using our secret key
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            
            # finding the user in the database based on the user_id in the token
            cnx = database.get_db_connection()
            if not cnx:
                return jsonify({"error": "Database connection failed"}), 500
                
            cursor = cnx.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (data['user_id'],))
            current_user = cursor.fetchone()

            if not current_user:
                return jsonify({'message': 'Token is invalid (user not found)!'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired! Please log in again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401
        finally:
            # we ensure that DB connection is closed even if errors happen
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'cnx' in locals() and cnx:
                cnx.close()

        # passing the 'current_user' dictionary (containing user_id, username, group)
        # to the guarded function eg., get_all_patients function
        return f(current_user, *args, **kwargs)

    return decorated