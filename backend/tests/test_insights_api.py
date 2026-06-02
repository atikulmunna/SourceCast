import uuid
from types import SimpleNamespace

import pytest

from app.api.v1 import insights
from app.schemas.insights import SavedInsightCreate


class FakeInsightService:
    calls = []

    def __init__(self, db):
        self.db = db

    async def list_insights(self, user_id, space_id):
        self.calls.append(("list", user_id, space_id))
        return []

    async def create_insight(self, user_id, data):
        self.calls.append(("create", user_id, data))
        return "created"

    async def delete_insight(self, user_id, insight_id):
        self.calls.append(("delete", user_id, insight_id))


@pytest.fixture(autouse=True)
def fake_service(monkeypatch):
    FakeInsightService.calls = []
    monkeypatch.setattr(insights, "InsightService", FakeInsightService)


@pytest.mark.asyncio
async def test_insight_routes_delegate_authenticated_scope() -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    space_id = uuid.uuid4()
    insight_id = uuid.uuid4()
    data = SavedInsightCreate(space_id=space_id, content="Useful evidence.")

    assert await insights.list_insights(space_id, user, object()) == []
    assert await insights.create_insight(data, user, object()) == "created"
    assert await insights.delete_insight(insight_id, user, object()) is None
    assert [call[0] for call in FakeInsightService.calls] == ["list", "create", "delete"]
    assert all(call[1] == user.id for call in FakeInsightService.calls)
