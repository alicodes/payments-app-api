from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pymongo import ASCENDING
from pymongo.errors import InvalidId
from bson import ObjectId
from datetime import datetime, timezone
from models.payments import Payment
from config.database import payments_collection, evidence_collection
from schema.schemas import list_serial

router = APIRouter()

# Helper function for ObjectId validation
def validate_object_id(id_str):
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID format.")

# GET Request
@router.get("/payments/")
async def get_payments(
    status: str = Query(None),
    search: str = Query(None),
    page: int = 1,
    size: int = 20,
    sort_by: str = Query("payee_last_name"),  # Default sort field
    sort_order: str = Query("asc")          # Default sort order
):
    # Perform status calculations
    now = datetime.now(timezone.utc)

    # Build the query
    query = {}
    if status:
        query["payee_payment_status"] = status

    # Handle search (different logic for email searches)
    if search:
        if "@" in search:
            query["payee_email"] = {"$regex": search, "$options": "i"}  # Case-insensitive email search
        else:
            query["$text"] = {"$search": search}

    # Ensure payee_due_date is updated based on current date
    payments_to_update = payments_collection.find({"payee_due_date": {"$exists": True}})
    for payment in payments_to_update:
        payee_due_date = payment["payee_due_date"]
        if isinstance(payee_due_date, datetime) and payee_due_date.tzinfo is None:
            payee_due_date = payee_due_date.replace(tzinfo=timezone.utc)

        new_status = payment["payee_payment_status"]
        if payee_due_date < now:
            new_status = "overdue"
        elif payee_due_date.date() == now.date():
            new_status = "due_now"

        if new_status != payment["payee_payment_status"]:
            payments_collection.update_one(
                {"_id": payment["_id"]},
                {"$set": {"payee_payment_status": new_status}},
            )

    # Determine sort direction
    sort_direction = ASCENDING if sort_order == "asc" else -1

    # Perform the query with pagination and sorting
    payments = (
        payments_collection.find(query)
        .sort(sort_by, sort_direction)  # Use sort_by and sort_order for sorting
        .skip((page - 1) * size)
        .limit(size)
    )

    # Calculate total count for the query
    total = payments_collection.count_documents(query)

    return {"total": total, "page": page, "size": size, "data": list_serial(payments)}

# Update Payment
@router.put("/payments/{payment_id}/")
async def update_payment(payment_id: str, payment_update: dict):
    payment_id = validate_object_id(payment_id)
    if payment_update.get("payee_payment_status") == "completed":
        evidence = evidence_collection.find_one({"payment_id": str(payment_id)})
        if not evidence:
            raise HTTPException(
                status_code=400,
                detail="Cannot mark payment as completed without evidence."
            )

    result = payments_collection.update_one({"_id": payment_id}, {"$set": payment_update})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return {"message": "Payment updated successfully."}

# Delete Payment
@router.delete("/payments/{payment_id}/")
async def delete_payment(payment_id: str):
    # Validate payment_id format
    payment_id = validate_object_id(payment_id)

    # Check if the payment exists
    payment = payments_collection.find_one({"_id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")

    # Check if the payment is completed before deleting evidence
    deleted_evidence_count = 0
    if payment["payee_payment_status"] == "completed":
        # Cascade delete evidence files
        evidence_result = evidence_collection.delete_many({"payment_id": str(payment_id)})
        deleted_evidence_count = evidence_result.deleted_count

    # Delete the payment record
    payment_result = payments_collection.delete_one({"_id": payment_id})

    # Return appropriate response
    if payment_result.deleted_count == 1:
        return {
            "message": "Payment deleted successfully.",
            "deleted_evidence_count": deleted_evidence_count,
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete the payment. Please try again later.",
        )

# Create Payment
@router.post("/payments/")
async def create_payment(payment: Payment):
    try:
        # Set default status to "pending"
        if payment.payee_payment_status != "pending":
            raise HTTPException(
                status_code=400, 
                detail="New payments must have a status of 'pending'."
            )

        # Validate due_date (cannot be in the past)
        if payment.payee_due_date < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400, 
                detail="The due date cannot be in the past."
            )

        # Validate discount and tax percentages
        if payment.discount_percent is not None and (payment.discount_percent < 0 or payment.discount_percent > 100):
            raise HTTPException(
                status_code=400, 
                detail="Discount percentage must be between 0 and 100."
            )
        if payment.tax_percent is not None and (payment.tax_percent < 0 or payment.tax_percent > 100):
            raise HTTPException(
                status_code=400, 
                detail="Tax percentage must be between 0 and 100."
            )

        # Calculate total_due if not provided
        payment.total_due = round(
            payment.due_amount * (1 - (payment.discount_percent or 0) / 100) * (1 + (payment.tax_percent or 0) / 100), 2
        )

        # Insert payment into MongoDB
        result = payments_collection.insert_one(payment.dict())

        return {
            "message": "Payment created successfully.",
            "payment_id": str(result.inserted_id),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while creating the payment: {e}",
        )

# Upload Evidence
@router.post("/payments/{payment_id}/upload-evidence/")
async def upload_evidence(payment_id: str, file: UploadFile = File(...)):
    if file.content_type not in ["application/pdf", "image/png", "image/jpeg"]:
        raise HTTPException(status_code=400, detail="Invalid file type.")

    # Validate and convert payment_id to ObjectId
    payment_id = validate_object_id(payment_id)

    # Check if the payment exists
    payment = payments_collection.find_one({"_id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")

    # Save the evidence file in MongoDB
    evidence_id = evidence_collection.insert_one({
        "payment_id": str(payment_id),  # Store as a string for consistency
        "filename": file.filename,
        "content": await file.read(),
    }).inserted_id

    # Update the payment status to 'completed'
    payments_collection.update_one(
        {"_id": payment_id},
        {"$set": {"payee_payment_status": "completed"}}
    )

    return {
        "message": "Evidence uploaded successfully and payment status updated to 'completed'.",
        "evidence_id": str(evidence_id),
    }

# Download Evidence
@router.get("/payments/{payment_id}/download-evidence/")
async def download_evidence(payment_id: str):
    payment_id = validate_object_id(payment_id)
    evidence = evidence_collection.find_one({"payment_id": str(payment_id)})
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    
    # Stream the file content
    return StreamingResponse(
        iter([evidence["content"]]),
        headers={"Content-Disposition": f'attachment; filename="{evidence["filename"]}"'},
    )