from app.services.conversation_store import ConversationStore
from app.services.retrieval_service import merge_packed_chunks, pages_to_pack, rerank_hits
from app.schemas.retrieval import RetrievedChunk
from app.utils.query import expand_retrieval_query, is_followup_question, lexical_overlap


def _chunk(chunk_id: str, page: int, text: str, distance: float, *, within: bool = True) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        document_title="Fixture",
        document_version="test",
        source_filename="fixture.pdf",
        page_number=page,
        excerpt=text[:40],
        distance=distance,
        text=text,
        within_threshold=within,
    )


def test_expands_csit_and_fee_intent() -> None:
    expanded = expand_retrieval_query("What are the fees for the CSIT department?").lower()
    assert "computer science and information technology" in expanded
    assert "tuition" in expanded
    assert "teaching departments" not in expanded


def test_department_list_query_expands_faculty_terms() -> None:
    expanded = expand_retrieval_query("How many departments are listed in the prospectus?").lower()
    assert "teaching departments" in expanded
    assert "faculties" in expanded


def test_does_not_expand_off_topic_questions() -> None:
    question = "What is the capital of France and the current weather in Paris?"
    assert expand_retrieval_query(question) == question


def test_followup_does_not_treat_standalone_questions_as_followups() -> None:
    assert is_followup_question("How many departments are there?", ["What are the CSIT fees?"]) is False
    assert is_followup_question("What about the hostel charges?", ["What are the CSIT fees?"]) is True


def test_conversation_store_keeps_standalone_questions_unmixed() -> None:
    store = ConversationStore()
    conversation = store.ensure("c1")
    store.append_user_question("c1", "What are the fees for the CSIT department?")
    conversation = store.ensure("c1")
    query = store.retrieval_query(conversation, "How many departments are there?")
    assert query == "How many departments are there?"
    follow = store.retrieval_query(conversation, "What about hostel charges?")
    assert "CSIT" in follow
    assert "hostel charges" in follow


def test_lexical_rerank_prefers_department_list_over_closer_unrelated_hit() -> None:
    query = expand_retrieval_query("List of departments in the prospectus")
    unrelated = _chunk("a", 112, "Medical Department is located next to Humanities.", 0.55)
    listed = _chunk(
        "b",
        15,
        "The teaching departments under various Faculties are listed below: Civil Engineering.",
        0.70,
    )
    ranked = rerank_hits([unrelated, listed], query)
    assert ranked[0].chunk_id == "b"


def test_chapter_pages_include_neighbor() -> None:
    heading = _chunk("h", 14, "CHAPTER Academic Programmes and Departments", 0.50)
    pages = pages_to_pack([heading])
    assert 14 in pages
    assert 15 in pages


def test_merge_packed_chunks_deduplicates_and_caps() -> None:
    selected = [_chunk("a", 100, "fee table", 0.4)]
    extras = [_chunk("a", 100, "fee table", 0.4), _chunk("b", 100, "tuition Rs.51170", 0.4)]
    merged = merge_packed_chunks(selected, extras, cap=14)
    assert [item.chunk_id for item in merged] == ["a", "b"]
