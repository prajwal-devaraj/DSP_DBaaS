from flask import Flask
import config
from flask_bcrypt import Bcrypt
from flask_cors import CORS

# creating the application instance
app = Flask(__name__)

# here this line tells our server to allow requests from any webpage
CORS(app) 

# loading the settings from config.py into the Flask app
app.config.from_object(config)

# initializing bycrypt
bcrypt = Bcrypt(app)

# import the routes so Flask knows about them
from app import routes

