from app.ingestion.chunker import TreeSitterChunker, extract_js_imports, extract_python_imports


def test_python_chunker_extracts_symbols_and_imports():
    content = """import os
from services.payment_service import PaymentService

class Checkout:
    def run(self):
        return PaymentService()

def helper():
    return os.getcwd()
"""
    chunks = TreeSitterChunker().chunk_file("api/payments.py", content)

    assert [chunk.symbols_defined for chunk in chunks] == [["Checkout"], ["helper"]]
    assert "services.payment_service" in chunks[0].imports


def test_typescript_chunker_extracts_functions_and_imports():
    content = """import { createUser } from "../db/users";

export async function registerUser(email: string) {
  return createUser(email);
}
"""
    chunks = TreeSitterChunker().chunk_file("services/registration.ts", content)

    assert chunks[0].symbols_defined == ["registerUser"]
    assert extract_js_imports(content) == ["../db/users"]


def test_extract_python_imports_handles_from_imports():
    assert extract_python_imports("from db.transaction_manager import transaction\n") == ["db.transaction_manager"]

