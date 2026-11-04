import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db
from app.main import create_app
from app.config.settings import Settings, get_settings
from app.config.dynamic_config import DynamicConfigManager, get_dynamic_config
from app.schemas.config import AutomationConfig

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        META_APP_ID="test_app_id_123",
        META_APP_SECRET="test_secret_abc123",
        VERIFY_TOKEN="test_verify_token_xyz",
        PAGE_ACCESS_TOKEN="test_page_access_token_token",
        INSTAGRAM_ACCOUNT_ID="17841400000000001",
        DATABASE_URL=TEST_DB_URL,
        CONFIG_PATH="./test_config.json",
        DEBUG=True,
    )


@pytest.fixture(scope="function")
def test_db_session():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_config():
    """Provide a fresh AutomationConfig instance."""
    return AutomationConfig(
        enabled=True,
        match_mode="partial",
        case_sensitive=False,
        keywords=["link", "guide", "pdf", "roadmap", "help"],
        reply_once_days=7,
        message_template="Hi {username}! Here is your {keyword}: https://example.com/info",
        max_retries=1,
    )


@pytest.fixture(scope="function")
def client(test_db_session, test_settings, tmp_path):
    """FastAPI TestClient with overridden DB and settings."""
    test_config_file = str(tmp_path / "test_config.json")
    test_settings.CONFIG_PATH = test_config_file

    app = create_app()

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    def override_get_settings():
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    with TestClient(app) as test_client:
        yield test_client

    if os.path.exists(test_config_file):
        os.remove(test_config_file)


@pytest.fixture
def sample_comment_webhook_payload():
    """Standard Meta Instagram Comment Webhook Payload."""
    return {
        "object": "instagram",
        "entry": [
            {
                "id": "17841400000000001",
                "time": 1730001122,
                "changes": [
                    {
                        "field": "comments",
                        "value": {
                            "id": "17999888777666",
                            "text": "Please send me the guide and link!",
                            "from": {
                                "id": "17841499999999",
                                "username": "alice_dev",
                            },
                            "media": {
                                "id": "18000111222333",
                                "media_product_type": "FEED",
                            },
                        },
                    }
                ],
            }
        ],
    }
