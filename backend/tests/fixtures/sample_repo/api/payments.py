from services.payment_service import PaymentService


def checkout(request):
    service = PaymentService()
    return service.authorize(request["amount"], request["user_id"])

