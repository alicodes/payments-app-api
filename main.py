from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ASCENDING, TEXT
from routes.route import router
import pandas as pd
from models.payments import Payment
from config.database import payments_collection, import_log_collection
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import os
from io import StringIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT is not set
    uvicorn.run(app, host="0.0.0.0", port=port)

# Load the encryption key from .env
load_dotenv()
key = os.getenv("ENCRYPTION_KEY")
if not key:
    raise ValueError("ENCRYPTION_KEY not found in the .env file")

fernet = Fernet(key.encode())

# Normalize and save data
def normalize_and_save(csv_file_path):
    try:
        # Check if the file has already been processed
        if import_log_collection.find_one({"file_name": csv_file_path}):
            print(f"The file '{csv_file_path}' has already been processed. Skipping insertion.")
            return

        # Read and decrypt the encrypted file
        with open(csv_file_path, "rb") as encrypted_file:
            encrypted_data = encrypted_file.read()
        decrypted_data = fernet.decrypt(encrypted_data)

        # Load the decrypted CSV content into a DataFrame
        df = pd.read_csv(StringIO(decrypted_data.decode()), keep_default_na=False)
        
        # Normalize data and validate using Pydantic
        payments = []
        for record in df.to_dict(orient="records"):
            record["payee_country"] = str(record["payee_country"])
            record["payee_postal_code"] = str(record["payee_postal_code"])
            record["payee_phone_number"] = str(record["payee_phone_number"])


            payment = Payment(**record)
            payment.total_due = round(
                payment.due_amount * (1 - payment.discount_percent / 100)
                * (1 + payment.tax_percent / 100), 2
            )
            payments.append(payment.dict())
        
        # Insert into MongoDB
        payments_collection.insert_many(payments)

        # Log the file as processed
        import_log_collection.insert_one({"file_name": csv_file_path})

        return {"message": "CSV data uploaded successfully!"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {e}")
    
# Function to create indexes if they don't already exist
def create_indexes():
    # List of indexes to ensure
    indexes_to_create = [
        {"fields": [("payee_payment_status", ASCENDING)], "name": "payment_status_index"},
        {"fields": [("payee_due_date", ASCENDING)], "name": "due_date_index"},
        {
            "fields": [
                ("payee_first_name", TEXT),
                ("payee_last_name", TEXT),
                ("payee_email", TEXT),
                ("payee_address_line_1", TEXT),
                ("payee_address_line_2", TEXT),
                ("payee_city", TEXT),
                ("payee_country", TEXT),
                ("payee_province_or_state", TEXT),
            ],
            "name": "all_text_fields_index",
        },
        {
            "fields": [
                ("payee_payment_status", ASCENDING),
                ("payee_due_date", ASCENDING),
            ],
            "name": "status_due_date_index",
        },
    ]

    # Get existing indexes
    existing_indexes = payments_collection.index_information()

    # Create missing indexes
    for index in indexes_to_create:
        if index["name"] not in existing_indexes:
            payments_collection.create_index(index["fields"], name=index["name"])
            print(f"Index '{index['name']}' created.")
        else:
            print(f"Index '{index['name']}' already exists. Skipping.")

# Decrypt and process the CSV file
result = normalize_and_save("payment_information.csv")

if result:
    print(result)

# Call the function to ensure indexes exist
create_indexes()