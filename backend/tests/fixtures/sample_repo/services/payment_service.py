from db.transaction_manager import transaction


class PaymentService:
    def authorize(self, amount, user_id):
        with transaction():
            return {"status": "authorized", "amount": amount, "user_id": user_id}

