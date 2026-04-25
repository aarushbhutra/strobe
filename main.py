from contextlib import asynccontextmanager
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import db.database as database

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    database.client = AsyncIOMotorClient(settings.MONGO_URI)
    database.db = database.client[settings.MONGO_DB]
    yield
    # Shutdown logic
    if database.client:
        database.client.close()
        database.client = None
        database.db = None

app = FastAPI(
    title="Strobe",
    description="Feature Flag & A/B Testing Service",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/health")
def health_check():
    return {"status": "ok", "db": settings.MONGO_DB}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
