import pytest
from unittest.mock import AsyncMock

from app.config.dynamic_config import DynamicConfigManager, get_dynamic_config
from app.models.comment import Comment
from app.models.dm_log import DMLog
from app.models.user import User
from app.schemas.config import AutomationConfig, AutomationConfigUpdate
from app.schemas.webhook import CommentEvent
from app.services.comment_processor import CommentProcessor
from app.services.duplicate_checker import DuplicateChecker
from app.services.keyword_matcher import KeywordMatcher
from app.services.meta_client import MetaClient


@pytest.fixture(autouse=True)
def reset_dynamic_config(tmp_path):
    cfg_file = str(tmp_path / "proc_config.json")
    mgr = DynamicConfigManager(config_path=cfg_file)
    DynamicConfigManager._instance = mgr
    yield mgr
    DynamicConfigManager._instance = None


@pytest.mark.asyncio
async def test_process_comment_success_flow(test_db_session, test_settings):
    mock_meta = AsyncMock(spec=MetaClient)
    mock_meta.send_dm.return_value = {"message_id": "mid_test_123"}

    processor = CommentProcessor(
        meta_client=mock_meta,
        keyword_matcher=KeywordMatcher(),
        duplicate_checker=DuplicateChecker(),
    )

    event = CommentEvent(
        comment_id="c_111",
        media_id="m_222",
        ig_user_id="u_333",
        username="john_tester",
        text="Please send me the guide link!",
    )

    dm_log = await processor.process_comment(event, test_db_session)

    assert dm_log is not None
    assert dm_log.status == "SUCCESS"
    assert "john_tester" in dm_log.message_sent

    # Verify database records
    user = test_db_session.query(User).filter(User.ig_user_id == "u_333").first()
    assert user is not None
    assert user.username == "john_tester"

    comment = test_db_session.query(Comment).filter(Comment.comment_id == "c_111").first()
    assert comment is not None
    assert comment.matched_keyword in ["link", "guide"]
    assert comment.is_processed is True

    # Verify Meta API call
    mock_meta.send_dm.assert_called_once()


@pytest.mark.asyncio
async def test_process_comment_no_keyword_match(test_db_session):
    mock_meta = AsyncMock(spec=MetaClient)
    processor = CommentProcessor(meta_client=mock_meta)

    event = CommentEvent(
        comment_id="c_no_match",
        media_id="m_222",
        ig_user_id="u_444",
        username="random_guy",
        text="Great picture brother!",
    )

    dm_log = await processor.process_comment(event, test_db_session)

    assert dm_log is None
    mock_meta.send_dm.assert_not_called()

    # Comment should still be saved
    comment = test_db_session.query(Comment).filter(Comment.comment_id == "c_no_match").first()
    assert comment is not None
    assert comment.matched_keyword is None


@pytest.mark.asyncio
async def test_process_comment_disabled_automation(test_db_session):
    mgr = get_dynamic_config()
    mgr.update(AutomationConfigUpdate(enabled=False))

    mock_meta = AsyncMock(spec=MetaClient)
    processor = CommentProcessor(meta_client=mock_meta)

    event = CommentEvent(
        comment_id="c_disabled",
        media_id="m_222",
        ig_user_id="u_555",
        username="disabled_test",
        text="send me the guide",
    )

    dm_log = await processor.process_comment(event, test_db_session)

    assert dm_log is not None
    assert dm_log.status == "SKIPPED_DISABLED"
    mock_meta.send_dm.assert_not_called()


@pytest.mark.asyncio
async def test_process_comment_duplicate_cooldown(test_db_session):
    mock_meta = AsyncMock(spec=MetaClient)
    mock_meta.send_dm.return_value = {"message_id": "mid_dup"}
    processor = CommentProcessor(meta_client=mock_meta)

    event1 = CommentEvent(
        comment_id="c_first",
        media_id="m_100",
        ig_user_id="u_dup",
        username="dup_user",
        text="send me the link",
    )
    first_log = await processor.process_comment(event1, test_db_session)
    assert first_log.status == "SUCCESS"

    # User comments again on another post within 7-day cooldown
    event2 = CommentEvent(
        comment_id="c_second",
        media_id="m_200",
        ig_user_id="u_dup",
        username="dup_user",
        text="can you send the guide please",
    )
    second_log = await processor.process_comment(event2, test_db_session)
    assert second_log is not None
    assert second_log.status == "SKIPPED_DUPLICATE"


@pytest.mark.asyncio
async def test_process_comment_idempotency(test_db_session):
    mock_meta = AsyncMock(spec=MetaClient)
    mock_meta.send_dm.return_value = {"message_id": "mid_idempotent"}
    processor = CommentProcessor(meta_client=mock_meta)

    event = CommentEvent(
        comment_id="c_same",
        media_id="m_100",
        ig_user_id="u_idempotent",
        username="idem_user",
        text="link please",
    )
    first_res = await processor.process_comment(event, test_db_session)
    assert first_res.status == "SUCCESS"

    # Exact same comment event arriving again (Meta webhook retry)
    second_res = await processor.process_comment(event, test_db_session)
    assert second_res is None
    # Meta client called only once
    assert mock_meta.send_dm.call_count == 1

