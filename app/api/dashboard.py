from datetime import datetime
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.dynamic_config import get_dynamic_config
from app.database.session import get_db
from app.models.comment import Comment
from app.models.dm_log import DMLog
from app.models.error_log import ErrorLog
from app.models.user import User
from app.schemas.stats import DashboardStats, DMLogItem, ErrorLogItem

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/v1/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)):
    """Fetch aggregated statistics and recent logs for automation metrics."""
    config = get_dynamic_config().get_config()

    total_comments = db.query(Comment).count()
    matched_comments = db.query(Comment).filter(Comment.matched_keyword.isnot(None)).count()

    dms_sent = db.query(DMLog).filter(DMLog.status == "SUCCESS").count()
    dms_failed = db.query(DMLog).filter(DMLog.status == "FAILED").count()
    dms_skipped_duplicate = db.query(DMLog).filter(DMLog.status == "SKIPPED_DUPLICATE").count()
    dms_skipped_disabled = db.query(DMLog).filter(DMLog.status == "SKIPPED_DISABLED").count()

    total_attempts = dms_sent + dms_failed
    success_rate = round((dms_sent / total_attempts * 100), 1) if total_attempts > 0 else 100.0

    recent_dm_records = (
        db.query(DMLog, User.username, User.ig_user_id)
        .outerjoin(User, DMLog.user_id == User.id)
        .order_by(DMLog.sent_at.desc())
        .limit(15)
        .all()
    )

    recent_logs: List[DMLogItem] = []
    for log, uname, ig_uid in recent_dm_records:
        recent_logs.append(
            DMLogItem(
                id=log.id,
                user_id=log.user_id,
                username=uname,
                ig_user_id=ig_uid,
                comment_id=log.comment_id,
                media_id=log.media_id,
                message_sent=log.message_sent,
                status=log.status,
                error_message=log.error_message,
                retry_count=log.retry_count,
                sent_at=log.sent_at,
            )
        )

    recent_error_records = (
        db.query(ErrorLog)
        .order_by(ErrorLog.created_at.desc())
        .limit(10)
        .all()
    )
    recent_errors = [ErrorLogItem.model_validate(err) for err in recent_error_records]

    return DashboardStats(
        total_comments=total_comments,
        matched_comments=matched_comments,
        dms_sent=dms_sent,
        dms_failed=dms_failed,
        dms_skipped_duplicate=dms_skipped_duplicate,
        dms_skipped_disabled=dms_skipped_disabled,
        success_rate_percent=success_rate,
        automation_enabled=config.enabled,
        active_keywords_count=len(config.keywords),
        recent_logs=recent_logs,
        recent_errors=recent_errors,
    )


@router.get("/dashboard", response_class=HTMLResponse)
def render_dashboard(db: Session = Depends(get_db)):
    """Render modern web dashboard for metrics, system health, and logs."""
    stats = get_stats(db)
    config = get_dynamic_config().get_config()

    rows_html = ""
    for log in stats.recent_logs:
        status_badge = {
            "SUCCESS": '<span class="badge badge-success">Delivered</span>',
            "FAILED": '<span class="badge badge-danger">Failed</span>',
            "SKIPPED_DUPLICATE": '<span class="badge badge-warning">Skipped (Duplicate)</span>',
            "SKIPPED_DISABLED": '<span class="badge badge-secondary">Disabled</span>',
        }.get(log.status, f'<span class="badge">{log.status}</span>')

        sent_time = log.sent_at.strftime("%Y-%m-%d %H:%M:%S")
        uname = f"@{log.username}" if log.username else f"ID: {log.ig_user_id or log.user_id}"
        msg_preview = (log.message_sent[:55] + "...") if log.message_sent and len(log.message_sent) > 55 else (log.message_sent or "-")
        err_msg = log.error_message or "-"

        rows_html += f"""
        <tr>
            <td>{log.id}</td>
            <td><strong>{uname}</strong></td>
            <td><code>{log.media_id}</code></td>
            <td>{status_badge}</td>
            <td><small>{msg_preview}</small></td>
            <td><small class="text-muted">{err_msg}</small></td>
            <td>{sent_time}</td>
        </tr>
        """

    if not rows_html:
        rows_html = '<tr><td colspan="7" class="text-center text-muted py-4">No DM activities logged yet. Waiting for incoming comments!</td></tr>'

    keywords_badges = "".join([f'<span class="kw-tag">{kw}</span>' for kw in config.keywords])

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram Auto DM Dashboard</title>
    <style>
        :root {{
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --bg: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --border: #334155;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background-color: var(--bg); color: var(--text-main); padding: 2rem 1.5rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1.25rem; }}
        h1 {{ font-size: 1.75rem; font-weight: 700; display: flex; align-items: center; gap: 0.5rem; }}
        .header-actions {{ display: flex; gap: 1rem; align-items: center; }}
        .status-pill {{ padding: 0.4rem 0.9rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; display: flex; align-items: center; gap: 0.4rem; }}
        .status-on {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }}
        .status-off {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }}
        .grid-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }}
        .stat-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }}
        .stat-label {{ color: var(--text-sub); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }}
        .stat-val {{ font-size: 1.85rem; font-weight: 700; }}
        .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }}
        .card-header {{ font-size: 1.15rem; font-weight: 600; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; }}
        .kw-container {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
        .kw-tag {{ background: rgba(79, 70, 229, 0.2); color: #818cf8; border: 1px solid #4f46e5; padding: 0.25rem 0.65rem; border-radius: 6px; font-size: 0.85rem; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem; }}
        th, td {{ padding: 0.85rem 1rem; border-bottom: 1px solid var(--border); }}
        th {{ color: var(--text-sub); font-weight: 600; background: rgba(0,0,0,0.15); }}
        .badge {{ padding: 0.25rem 0.55rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }}
        .badge-success {{ background: rgba(16, 185, 129, 0.2); color: var(--success); }}
        .badge-warning {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); }}
        .badge-danger {{ background: rgba(239, 68, 68, 0.2); color: var(--danger); }}
        .badge-secondary {{ background: rgba(148, 163, 184, 0.2); color: var(--text-sub); }}
        code {{ background: rgba(0,0,0,0.3); padding: 0.2rem 0.4rem; border-radius: 4px; font-family: monospace; font-size: 0.8rem; }}
        .btn {{ padding: 0.5rem 1rem; border-radius: 6px; font-weight: 600; cursor: pointer; border: none; transition: 0.2s; font-size: 0.85rem; text-decoration: none; }}
        .btn-primary {{ background: var(--primary); color: white; }}
        .btn-primary:hover {{ background: var(--primary-hover); }}
        .refresh-btn {{ background: #334155; color: white; }}
        .refresh-btn:hover {{ background: #475569; }}
        .text-center {{ text-align: center; }}
        .text-muted {{ color: var(--text-sub); }}
        .py-4 {{ padding-top: 1.5rem; padding-bottom: 1.5rem; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>📸 Instagram Auto DM Automation</h1>
                <p class="text-muted" style="margin-top: 0.25rem;">Meta Graph API Compliant &bull; Real-time Webhook Processing</p>
            </div>
            <div class="header-actions">
                <span class="status-pill {"status-on" if stats.automation_enabled else "status-off"}">
                    {"● Automation Active" if stats.automation_enabled else "○ Automation Disabled"}
                </span>
                <button class="btn refresh-btn" onclick="window.location.reload()">↻ Refresh</button>
                <a href="/docs" target="_blank" class="btn btn-primary">Swagger Docs</a>
            </div>
        </header>

        <div class="grid-stats">
            <div class="stat-card">
                <div class="stat-label">Total Comments</div>
                <div class="stat-val">{stats.total_comments}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Keyword Matches</div>
                <div class="stat-val" style="color: #818cf8;">{stats.matched_comments}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">DMs Delivered</div>
                <div class="stat-val" style="color: var(--success);">{stats.dms_sent}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Duplicates Skipped</div>
                <div class="stat-val" style="color: var(--warning);">{stats.dms_skipped_duplicate}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Delivery Failures</div>
                <div class="stat-val" style="color: var(--danger);">{stats.dms_failed}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Success Rate</div>
                <div class="stat-val">{stats.success_rate_percent}%</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <span>Active Keywords & Cooldown</span>
                <small class="text-muted">Cooldown: {config.reply_once_days} days &bull; Match Mode: {config.match_mode}</small>
            </div>
            <div class="kw-container">
                {keywords_badges}
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <span>Recent Outbound DM Activity</span>
                <small class="text-muted">Showing latest 15 transactions</small>
            </div>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Recipient</th>
                            <th>Media ID</th>
                            <th>Status</th>
                            <th>Message Preview</th>
                            <th>Notes / Error</th>
                            <th>Sent At (UTC)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content)
