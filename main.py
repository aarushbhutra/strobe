from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
from api.limiter import limiter
import db.database as database


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.client = AsyncIOMotorClient(settings.MONGO_URI)
    database.db = database.client[settings.MONGO_DB]
    database.flags = database.FlagRepository(database.db)
    database.audit = database.AuditRepository(database.db)

    await database.flags.setup_indexes(flag_ttl_days=settings.FLAG_TTL_DAYS)

    yield

    if database.client:
        database.client.close()
        database.client = None
        database.db = None
        database.flags = None
        database.audit = None


app = FastAPI(
    title="Strobe",
    description="Free, open feature flag & A/B testing service. Rate limits: 10 writes/min, 60 reads/min, 120 evaluations/min per IP.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.flags import router as flags_router
from api.evaluate import router as evaluate_router

app.include_router(flags_router)
app.include_router(evaluate_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "db": settings.MONGO_DB}


@app.get("/")
def read_root():
    return {
        "message": "Welcome to Strobe — free feature flag & A/B testing API.",
        "docs": "/docs",
        "limits": {
            "max_flags": settings.MAX_FLAGS,
            "flag_ttl_days": settings.FLAG_TTL_DAYS,
            "rate_limit_writes": "10/minute",
            "rate_limit_reads": "60/minute",
            "rate_limit_evaluate": "120/minute",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
