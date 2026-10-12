from tests.test_api import MEMBER, patched, text_pdf, upload  # noqa: F401
from tests.test_tiers import client  # noqa: F401


def test_long_earlier_answers_are_trimmed_not_rejected(client):
    doc = upload(client, text_pdf(), headers={}).json()["doc_id"]
    long = "x" * 6000
    history = [{"role": "assistant", "text": long}]
    r = client.post("/ask", json={"doc_ids": [doc], "question": "payment", "history": history})
    assert r.status_code == 200


def test_guest_file_and_member_file_work_in_one_question(client):
    ip = {"x-forwarded-for": "9.9.9.9"}
    guest_doc = upload(client, text_pdf(), headers=ip).json()["doc_id"]
    member_doc = upload(client, b"a,b\n1,2\n3,4\n", name="Iris.csv", headers={**MEMBER, **ip}).json()["doc_id"]
    r = client.post("/ask", json={"doc_ids": [guest_doc, member_doc], "question": "payment due"}, headers={**MEMBER, **ip})
    assert r.status_code == 200
