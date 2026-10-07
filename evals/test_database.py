from sqlalchemy import select, func
from backend import db
from backend.init_db import init_db

def test_idempotent_seed(tmp_path, monkeypatch):
    from sqlalchemy.orm import sessionmaker
    engine=db.make_engine('sqlite:///'+str(tmp_path/'test.db'))
    monkeypatch.setattr(db,'engine',engine)
    monkeypatch.setattr(db,'Session',sessionmaker(bind=engine,expire_on_commit=False))
    init_db(); init_db()
    with db.Session() as session:
        assert session.scalar(select(func.count()).select_from(db.Case)) == 12
        assert all(c.data['label']=='synthetic seed' for c in session.scalars(select(db.Case)))
    assert {'users','cases','document_chunks','llm_usage','llm_cache'} <= set(db.Base.metadata.tables)
