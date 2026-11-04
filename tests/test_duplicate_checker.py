from datetime import datetime, timedelta
import pytest
from app.models.dm_log import DMLog
from app.models.user import User
from app.services.duplicate_checker import DuplicateChecker


def test_duplicate_checker_no_previous_logs(test_db_session):
    user = User(ig_user_id="user_123", username="john_doe")
    test_db_session.add(user)
    test_db_session.commit()

    is_dup = DuplicateChecker.is_duplicate(
        db=test_db_session,
        user_id=user.id,
        media_id="media_101",
        cooldown_days=7,
    )
    assert is_dup is False


def test_duplicate_checker_recent_success_is_duplicate(test_db_session):
    user = User(ig_user_id="user_456", username="jane_dev")
    test_db_session.add(user)
    test_db_session.commit()

    # Log a successful DM 2 days ago
    dm_log = DMLog(
        user_id=user.id,
        media_id="media_101",
        status="SUCCESS",
        sent_at=datetime.utcnow() - timedelta(days=2),
    )
    test_db_session.add(dm_log)
    test_db_session.commit()

    # Within 7-day cooldown -> should be duplicate
    is_dup = DuplicateChecker.is_duplicate(
        db=test_db_session,
        user_id=user.id,
        media_id="media_101",
        cooldown_days=7,
    )
    assert is_dup is True


def test_duplicate_checker_expired_cooldown(test_db_session):
    user = User(ig_user_id="user_789", username="bob_coder")
    test_db_session.add(user)
    test_db_session.commit()

    # Log a successful DM 10 days ago
    dm_log = DMLog(
        user_id=user.id,
        media_id="media_101",
        status="SUCCESS",
        sent_at=datetime.utcnow() - timedelta(days=10),
    )
    test_db_session.add(dm_log)
    test_db_session.commit()

    # 10 days ago > 7 days cooldown -> should NOT be duplicate
    is_dup = DuplicateChecker.is_duplicate(
        db=test_db_session,
        user_id=user.id,
        media_id="media_101",
        cooldown_days=7,
    )
    assert is_dup is False


def test_duplicate_checker_failed_dm_not_counted_as_duplicate(test_db_session):
    user = User(ig_user_id="user_failed", username="fail_tester")
    test_db_session.add(user)
    test_db_session.commit()

    # Log a FAILED DM from 1 day ago
    dm_log = DMLog(
        user_id=user.id,
        media_id="media_101",
        status="FAILED",
        sent_at=datetime.utcnow() - timedelta(days=1),
    )
    test_db_session.add(dm_log)
    test_db_session.commit()

    # Failed DM should not block user from getting DM on retry
    is_dup = DuplicateChecker.is_duplicate(
        db=test_db_session,
        user_id=user.id,
        media_id="media_101",
        cooldown_days=7,
    )
    assert is_dup is False


def test_duplicate_checker_media_specific_flag(test_db_session):
    user = User(ig_user_id="user_multi_media", username="media_fan")
    test_db_session.add(user)
    test_db_session.commit()

    # Successful DM for post A
    dm_log = DMLog(
        user_id=user.id,
        media_id="post_A",
        status="SUCCESS",
        sent_at=datetime.utcnow() - timedelta(days=1),
    )
    test_db_session.add(dm_log)
    test_db_session.commit()

    # Check for post B with media_specific=True -> not duplicate
    is_dup = DuplicateChecker.is_duplicate(
        db=test_db_session,
        user_id=user.id,
        media_id="post_B",
        cooldown_days=7,
        media_specific=True,
    )
    assert is_dup is False

    # Check for post A with media_specific=True -> IS duplicate
    is_dup_same = DuplicateChecker.is_duplicate(
        db=test_db_session,
        user_id=user.id,
        media_id="post_A",
        cooldown_days=7,
        media_specific=True,
    )
    assert is_dup_same is True
