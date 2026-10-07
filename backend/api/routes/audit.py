"""Audit-log viewer (admins only): filter by user, action and date range, newest first, paginated."""
from datetime import date, datetime, time, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from backend import db
from backend.auth import require

router = APIRouter(prefix='/api/audit', tags=['audit'])


def _day(value, end=False):
    if not value:
        return None
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, 'Dates must be YYYY-MM-DD')
    start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    return start + timedelta(days=1) if end else start


@router.get('')
def audit_log(user_id: str | None = None, action: str | None = None, date_from: str | None = None, date_to: str | None = None,
              limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), user=Depends(require('users'))):
    from backend.services.workflow import user_names
    query = select(db.AuditLog)
    if user_id: query = query.where(db.AuditLog.user_id == user_id)
    if action: query = query.where(db.AuditLog.action == action)
    if date_from: query = query.where(db.AuditLog.created_at >= _day(date_from))
    if date_to: query = query.where(db.AuditLog.created_at < _day(date_to, end=True))
    with db.Session() as s:
        total = s.scalar(select(func.count()).select_from(query.subquery()))
        rows = list(s.scalars(query.order_by(db.AuditLog.created_at.desc(), db.AuditLog.id.desc()).limit(limit).offset(offset)))
        names = user_names(s, [r.user_id for r in rows])
        actions = sorted(s.scalars(select(db.AuditLog.action).distinct()))
        users = [{'id': u.id, 'name': n} for u, n in ((u, user_names(s, [u.id]).get(u.id)) for u in s.scalars(select(db.User).order_by(db.User.email)))]
        return {'total': total, 'limit': limit, 'offset': offset, 'actions': actions, 'users': users,
                'items': [{'id': r.id, 'created_at': r.created_at, 'user_id': r.user_id, 'user_name': names.get(r.user_id),
                           'action': r.action, 'data': r.data} for r in rows]}
