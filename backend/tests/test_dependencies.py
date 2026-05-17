from app.ingestion.dependencies import resolve_dependency


def test_resolves_python_absolute_import():
    known = {"services/payment_service.py", "api/payments.py"}

    assert resolve_dependency("services.payment_service", "api/payments.py", known) == "services/payment_service.py"


def test_resolves_typescript_relative_import():
    known = {"services/registration.ts", "db/users.ts"}

    assert resolve_dependency("../db/users", "services/registration.ts", known) == "db/users.ts"

