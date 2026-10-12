import pymupdf
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.quota import quota
from app.store import store
from tests.test_api import MEMBER, patched, text_pdf, upload  # noqa: F401


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def pages_pdf(count):
    doc = pymupdf.open()
    for number in range(count):
        doc.new_page().insert_text((72, 100), f"Page {number + 1} has enough readable text for extraction to keep it as text.")
    data = doc.tobytes()
    doc.close()
    return data


def test_guests_can_only_upload_pdfs(client):
    response = upload(client, b"a,b\n1,2", name="data.csv", headers={})
    assert response.status_code == 403 and "Sign in" in response.json()["detail"]


def test_members_can_upload_other_types(client):
    assert upload(client, b"a,b\n1,2\n3,4", name="data.csv", headers=MEMBER).status_code == 200


def test_an_invalid_token_is_treated_as_a_guest(client):
    response = upload(client, b"a,b\n1,2", name="data.csv", headers={"authorization": "Bearer nonsense"})
    assert response.status_code == 403


def test_guest_size_limit_and_member_size_limit(client):
    big = b"%PDF-" + bytes(11 * 1024 * 1024)
    guest = upload(client, big, headers={})
    assert guest.status_code == 413 and "10 MB" in guest.json()["detail"] and "Sign in" in guest.json()["detail"]

    text = ("A line of readable text for the big file test.\n" * 280_000).encode()
    assert len(text) > 11 * 1024 * 1024
    member = upload(client, text, name="big.txt", headers=MEMBER)
    assert member.status_code == 200


def test_guest_pages_are_capped_and_members_get_more(client):
    pdf = pages_pdf(30)
    guest = upload(client, pdf, headers={}).json()
    assert guest["pages"] == 30 and guest["pages_processed"] == 25 and guest["truncated"] is True and guest["member"] is False
    member = upload(client, pdf, headers=MEMBER).json()
    assert member["pages_processed"] == 30 and member["truncated"] is False and member["member"] is True


def test_guest_question_cap_does_not_apply_to_members(client, monkeypatch):
    monkeypatch.setattr(config, "GUEST_QUESTIONS_PER_DAY", 2)
    monkeypatch.setattr(quota, "user_rpm", 1000)
    guest_doc = upload(client, text_pdf(), headers={}).json()["doc_id"]
    codes = [client.post("/ask", json={"doc_id": guest_doc, "question": "payment"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    body = client.post("/ask", json={"doc_id": guest_doc, "question": "payment"}).json()
    assert body["reason"] == "guest_cap"

    member_doc = upload(client, text_pdf(), headers=MEMBER).json()["doc_id"]
    codes = [client.post("/ask", json={"doc_id": member_doc, "question": "payment"}, headers=MEMBER).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 200]


def test_guest_upload_limit(client, monkeypatch):
    monkeypatch.setattr(config, "GUEST_UPLOADS_PER_DAY", 1)
    assert upload(client, text_pdf(), headers={}).status_code == 200
    assert upload(client, text_pdf(), headers={}).status_code == 429


def test_a_document_uploaded_as_a_guest_still_works_after_signing_in(client):
    doc_id = upload(client, text_pdf(), headers={}).json()["doc_id"]
    response = client.post("/ask", json={"doc_id": doc_id, "question": "payment"}, headers=MEMBER)
    assert response.status_code == 200


def test_another_member_cannot_read_a_members_document(client, monkeypatch):
    doc_id = upload(client, text_pdf(), headers=MEMBER).json()["doc_id"]
    monkeypatch.setattr(auth_module(), "verify", lambda token: {"sub": "someone-else"} if token == "other" else None)
    response = client.post("/ask", json={"doc_id": doc_id, "question": "hi"}, headers={"authorization": "Bearer other"})
    assert response.status_code == 404


def auth_module():
    from app import auth

    return auth


def test_quota_endpoint_reports_the_tier(client):
    assert client.get("/quota", headers=MEMBER).json()["member"] is True
    assert client.get("/quota").json()["member"] is False
