from motor.motor_asyncio import AsyncIOMotorClient

from db.repository import AuditRepository, FlagRepository

# These will be initialized in the lifespan context manager
client: AsyncIOMotorClient | None = None
db = None
flags: FlagRepository | None = None
audit: AuditRepository | None = None

def get_db():
    return db
