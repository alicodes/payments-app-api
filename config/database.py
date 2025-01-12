from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Retrieve the MongoDB connection string
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    raise ValueError("MONGO_URI not found in environment variables")

# Initialize MongoDB client
client = MongoClient(mongo_uri)

# Define database and collections
db = client.payment_db
payments_collection = db.payments
evidence_collection = db.evidence
import_log_collection = db.import_log  # Collection to track CSV imports

print("MongoDB connection established successfully.")