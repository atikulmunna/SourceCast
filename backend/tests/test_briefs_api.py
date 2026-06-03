import uuid
from types import SimpleNamespace

import pytest

from app.api.v1 import briefs
from app.schemas.briefs import ResearchBriefCreate


class FakeBriefService:
    calls = []

    def __init__(self, db):
        self.db = db

    async def list_briefs(self, user_id, space_id):
        self.calls.append(("list", user_id, space_id))
        return []

    async def create_brief(self, user_id, data):
        self.calls.append(("create", user_id, data))
        return "created"

    async def get_brief(self, user_id, brief_id):
        self.calls.append(("get", user_id, brief_id))
        return "brief"

    async def export_markdown(self, user_id, brief_id):
        self.calls.append(("export", user_id, brief_id))
        return "research.md", "# Research"

    async def delete_brief(self, user_id, brief_id):
        self.calls.append(("delete", user_id, brief_id))


@pytest.fixture(autouse=True)
def fake_service(monkeypatch):
    FakeBriefService.calls = []
    monkeypatch.setattr(briefs, "BriefService", FakeBriefService)


@pytest.mark.asyncio
async def test_brief_routes_delegate_authenticated_scope() -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    space_id = uuid.uuid4()
    brief_id = uuid.uuid4()
    data = ResearchBriefCreate(space_id=space_id, title="Brief")

    assert await briefs.list_briefs(space_id, user, object()) == []
    assert await briefs.create_brief(data, user, object()) == "created"
    assert await briefs.get_brief(brief_id, user, object()) == "brief"
    response = await briefs.export_brief_markdown(brief_id, user, object())
    assert response.body == b"# Research"
    assert response.headers["content-disposition"] == 'attachment; filename="research.md"'
    assert await briefs.delete_brief(brief_id, user, object()) is None
    assert [call[0] for call in FakeBriefService.calls] == [
        "list",
        "create",
        "get",
        "export",
        "delete",
    ]
    assert all(call[1] == user.id for call in FakeBriefService.calls)
