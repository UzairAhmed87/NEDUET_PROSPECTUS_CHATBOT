def test_health_endpoint(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["embedding_provider"] == "fake"


def test_chat_empty_query(client) -> None:
    response = client.post("/api/v1/chat", json={"question": "   "})
    assert response.status_code == 422


def test_ingest_requires_admin_key(client) -> None:
    response = client.post("/api/v1/documents/ingest", files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")})
    assert response.status_code == 401


def test_ingest_and_chat_roundtrip(client, fixture_pdf) -> None:
    with fixture_pdf.open("rb") as handle:
        ingest = client.post(
            "/api/v1/documents/ingest",
            files={"file": ("fixture.pdf", handle, "application/pdf")},
            data={"title": "NED Test Fixture", "academic_year": "2024-25"},
            headers={"X-Admin-Key": "test-admin-key-not-default"},
        )
    assert ingest.status_code == 200, ingest.text
    listed = client.get("/api/v1/documents")
    assert listed.status_code == 200
    assert listed.json()["documents"]

    chat = client.post("/api/v1/chat", json={"question": "Which undergraduate programmes are listed?"})
    assert chat.status_code == 200, chat.text
    payload = chat.json()
    assert payload["insufficient_evidence"] is False
    assert payload["citations"]
    assert payload["citations"][0]["page_number"] >= 1


def test_debug_retrieval_requires_admin(client) -> None:
    denied = client.post("/api/v1/retrieval/debug", json={"question": "programmes"})
    assert denied.status_code == 401
    allowed = client.post(
        "/api/v1/retrieval/debug",
        json={"question": "programmes"},
        headers={"X-Admin-Key": "test-admin-key-not-default"},
    )
    assert allowed.status_code == 200
