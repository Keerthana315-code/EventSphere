
from uuid import uuid4
from datetime import datetime, timezone


class PaymentService:

    @staticmethod
    def process_payment(amount: float):
        if amount <= 0:
            return {
                "success": False,
                "message": "Invalid payment amount"
            }

        payment_reference = "ES-PAY-" + uuid4().hex[:12].upper()

        return {
            "success": True,
            "payment_reference": payment_reference,
            "amount": amount,
            "status": "paid",
            "paid_at": datetime.now(timezone.utc).isoformat()
        }

    @staticmethod
    def refund_payment(payment_reference: str):
        if not payment_reference:
            return {
                "success": False,
                "message": "Payment reference not found"
            }

        return {
            "success": True,
            "refund_reference": "ES-REF-" + uuid4().hex[:12].upper(),
            "original_payment_reference": payment_reference,
            "status": "refunded"
        }
