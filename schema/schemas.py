def individual_serial(payment) -> dict:
    return {
        "id": str(payment["_id"]),
        "payee_first_name": payment['payee_first_name'],
        "payee_last_name": payment['payee_last_name'],
        "payee_payment_status": payment["payee_payment_status"],
        "payee_added_date_utc": payment["payee_added_date_utc"],
        "payee_due_date": payment["payee_due_date"],
        "payee_address_line_1": payment["payee_address_line_1"],
        "payee_address_line_2": payment.get("payee_address_line_2", ""),
        "payee_city": payment["payee_city"],
        "payee_province_or_state": payment.get("payee_province_or_state", ""),
        "payee_postal_code": payment["payee_postal_code"],
        "payee_country": payment["payee_country"],
        "payee_phone_number": payment["payee_phone_number"],
        "payee_email": payment["payee_email"],
        "currency": payment["currency"],
        "discount_percent": payment.get("discount_percent", 0),
        "tax_percent": payment.get("tax_percent", 0),
        "due_amount": payment["due_amount"],
        "total_due": payment["total_due"],
    }

def list_serial(payments) -> list:
    return [individual_serial(payment) for payment in payments]