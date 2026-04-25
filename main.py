from fastapi import FastAPI
from config import settings

app = FastAPI(
    title="Strobe",
    description="Feature Flag & A/B Testing Service",
    version="1.0.0",
)

@app.get("/health")
def health_check():
    return {"status": "ok", "db": settings.MONGO_DB}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
