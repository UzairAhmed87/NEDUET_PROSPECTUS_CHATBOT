def test_query_retrieves_expected_page(services, fixture_pdf) -> None:
    services["ingestion"].ingest_path(fixture_pdf, title="NED Test Fixture")
    result = services["retrieval"].retrieve("What undergraduate programmes are listed?")
    assert result.insufficient_evidence is False
    pages = {hit.page_number for hit in result.accepted}
    assert 1 in pages


def test_eligibility_question_hits_page_two(services, fixture_pdf) -> None:
    services["ingestion"].ingest_path(fixture_pdf, title="NED Test Fixture")
    result = services["retrieval"].retrieve("What are the admission eligibility requirements?")
    pages = [hit.page_number for hit in result.accepted]
    assert 2 in pages[:4]


def test_off_topic_query_is_insufficient(services, fixture_pdf) -> None:
    services["ingestion"].ingest_path(fixture_pdf, title="NED Test Fixture")
    result = services["retrieval"].retrieve("What is the capital of France and the current weather in Paris?")
    assert result.insufficient_evidence is True
