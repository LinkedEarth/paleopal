from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, constr
from typing import List, Dict, Any
from services.service_manager import service_manager

router = APIRouter(prefix="/api/sparql", tags=["sparql"])

class QueryRequest(BaseModel):
    query: constr(min_length=1)
    limit: int = 100
    offset: int = 0

@router.post("/run")
async def run_query(req: QueryRequest) -> Dict[str, Any]:
    """Run a SPARQL query with LIMIT/OFFSET on the backend so the
    frontend can page results without increasing chat size."""
    try:
        # Ensure the original query does not already have LIMIT/OFFSET
        paged_query = f"{req.query.strip()} LIMIT {req.limit} OFFSET {req.offset}"
        sparql_service = service_manager.get_sparql_service()
        raw = sparql_service.execute_query(paged_query)
        # convert bindings to simple dict list
        simple_rows: List[Dict[str, Any]] = []
        if "results" in raw and "bindings" in raw["results"]:
            vars_ = raw.get("head", {}).get("vars", [])
            for b in raw["results"]["bindings"]:
                row: Dict[str, Any] = {}
                for v in vars_:
                    if v in b:
                        row[v] = b[v]["value"]
                    else:
                        row[v] = None
                simple_rows.append(row)
        return {"rows": simple_rows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) 