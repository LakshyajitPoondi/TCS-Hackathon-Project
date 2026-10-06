from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/evals", tags=["evals"])


@router.get("")
def run_evals():
    raise HTTPException(status_code=501, detail="Implemented in Phase 5")
