from fastapi import APIRouter, HTTPException, Request
from models.evaluation import EvaluationContext, EvaluationResult, BulkEvaluationRequest, BulkEvaluationResponse
import db.database as database
from engine.evaluator import FlagEvaluator
from api.limiter import limiter
from api.auth import ApiKeyDep

router = APIRouter(prefix="/evaluate", tags=["evaluate"], dependencies=[ApiKeyDep])
evaluator = FlagEvaluator()


@router.post("/bulk", response_model=BulkEvaluationResponse)
@limiter.limit("120/minute")
async def evaluate_bulk(request: Request, body: BulkEvaluationRequest):
    if not body.flag_keys:
        flags = await database.flags.get_all_enabled()
    else:
        flags = await database.flags.get_many_by_keys(body.flag_keys)

    results = {}
    for flag in flags:
        results[flag.key] = evaluator.evaluate(flag, body.context)

    return BulkEvaluationResponse(results=results)


@router.post("/{flag_key}", response_model=EvaluationResult)
@limiter.limit("120/minute")
async def evaluate_flag(request: Request, flag_key: str, context: EvaluationContext):
    flag = await database.flags.get_by_key(flag_key)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    return evaluator.evaluate(flag, context)
