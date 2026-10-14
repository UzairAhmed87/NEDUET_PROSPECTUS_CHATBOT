from app.utils.hashing import document_id_from, sha256_bytes, slugify


def test_sha256_is_stable() -> None:
    payload = b"%PDF-1.4 test"
    assert sha256_bytes(payload) == sha256_bytes(payload)
    assert sha256_bytes(payload) != sha256_bytes(payload + b"x")


def test_document_id_uses_hash_prefix() -> None:
    digest = sha256_bytes(b"hello")
    doc_id = document_id_from("NED Prospectus.pdf", digest)
    assert digest[:12] in doc_id
    assert "ned" in doc_id


def test_slugify_strips_unsafe_characters() -> None:
    assert slugify("A / B \\ C") == "a-b-c"
