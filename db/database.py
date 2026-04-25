from motor.motor_asyncio import AsyncIOMotorClient

# These will be initialized in the lifespan context manager
client: AsyncIOMotorClient | None = None
db = None

def get_db():
    return db
