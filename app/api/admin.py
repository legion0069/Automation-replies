import logging
from fastapi import APIRouter, Depends
from app.api.deps import verify_admin_key
from app.config.dynamic_config import get_dynamic_config
from app.schemas.config import AutomationConfig, AutomationConfigUpdate

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_admin_key)])


@router.get("", response_model=AutomationConfig)
def get_settings():
    """Retrieve current dynamic automation settings."""
    config_mgr = get_dynamic_config()
    return config_mgr.get_config()


@router.post("", response_model=AutomationConfig)
def update_settings(update_data: AutomationConfigUpdate):
    """Update dynamic automation settings and persist to config.json immediately."""
    config_mgr = get_dynamic_config()
    updated = config_mgr.update(update_data)
    logger.info("Admin updated automation configuration.")
    return updated


@router.post("/reload", response_model=AutomationConfig)
def reload_settings():
    """Reload configuration from disk (config.json)."""
    config_mgr = get_dynamic_config()
    reloaded = config_mgr.reload()
    logger.info("Admin reloaded configuration from disk.")
    return reloaded


@router.post("/toggle", response_model=AutomationConfig)
def toggle_automation():
    """Toggle automation master switch (enabled/disabled)."""
    config_mgr = get_dynamic_config()
    current = config_mgr.get_config()
    updated = config_mgr.update(AutomationConfigUpdate(enabled=not current.enabled))
    logger.info("Admin toggled automation enabled status to: %s", updated.enabled)
    return updated
