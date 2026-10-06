from fastapi import APIRouter, HTTPException

from engine.rag import SOP_INDEX

router = APIRouter(prefix="/api/sops", tags=["sops"])


@router.get("/{sop_id}")
def get_sop(sop_id: str):
    # Lookup by known id only; the input never becomes a filesystem path (no traversal).
    sop = SOP_INDEX.get(sop_id)
    if sop is None:
        raise HTTPException(status_code=404, detail=f"SOP '{sop_id}' not found")
    return {"id": sop["id"], "title": sop["title"], "content": sop["text"]}
