"""
MongoDB database wrapper.

Usage:
    from core.database import db
    await db.add_user(user_id)
    await db.is_premium_user(user_id)
    ...

If ``MONGO_URL`` is not configured, the wrapper starts in a "dummy" mode where
every read returns a safe default and writes are no-ops. This lets the bot
boot for local/quick testing even without a database, while production (which
always sets MONGO_URL) gets the real behaviour.
"""
from datetime import datetime

from config import Config
from core.logger import get_logger

logger = get_logger(__name__)

_DB_NAME = "PosterBot"


class Database:
    def __init__(self, uri, database_name):
        self._uri = uri
        self._database_name = database_name
        self._available = bool(uri)
        self._client = None
        self.db = None
        self.col = None
        self.premium = None
        self.authorized = None
        self.user_settings = None

        if not uri:
            logger.warning("MONGO_URL not set — running in dummy (no-persist) DB mode.")
            return

        try:
            import motor.motor_asyncio
            self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
            self.db = self._client[database_name]
            self.col = self.db.users
            self.premium = self.db.premium_users
            self.authorized = self.db.authorized_users
            self.user_settings = self.db.user_settings
            self._available = True
        except Exception as e:
            self._available = False
            logger.error(f"DB init failed: {e}")

    # ── Helpers ────────────────────────────────────────────────────────────
    def _a(self, collection, method, *args, **kwargs):
        """Run a collection method safely; return None in dummy mode."""
        if not self._available or collection is None:
            return None
        try:
            return getattr(collection, method)(*args, **kwargs)
        except Exception as e:
            logger.error(f"DB {method} error: {e}")
            return None

    def new_user(self, id):
        return dict(id=id)

    # ── Users ──────────────────────────────────────────────────────────────
    async def add_user(self, id):
        if not self._available:
            return False
        try:
            user = await self.col.find_one({"id": int(id)})
            if not user:
                await self.col.insert_one(self.new_user(id))
                return True
        except Exception as e:
            logger.error(f"DB Error in add_user: {e}")
        return False

    async def is_user_exist(self, id):
        if not self._available:
            return False
        try:
            return bool(await self.col.find_one({"id": int(id)}))
        except Exception as e:
            logger.error(f"DB Error in is_user_exist: {e}")
            return False

    async def total_users_count(self):
        if not self._available:
            return 0
        return await self.col.count_documents({})

    async def get_all_users(self):
        if not self._available:
            return iter(())
        return self.col.find({})

    async def delete_user(self, user_id):
        if not self._available:
            return
        await self.col.delete_many({"id": int(user_id)})

    # ── Premium ────────────────────────────────────────────────────────────
    async def add_premium_user(self, user_id, rank, expiry_time):
        if not self._available:
            return
        await self.premium.update_one(
            {"user_id": user_id},
            {"$set": {"rank": rank, "expiry_time": expiry_time}},
            upsert=True,
        )

    async def remove_premium_user(self, user_id):
        if not self._available:
            return
        await self.premium.delete_one({"user_id": user_id})

    async def get_premium_user(self, user_id):
        if not self._available:
            return None
        return await self.premium.find_one({"user_id": user_id})

    async def is_premium_user(self, user_id):
        user = await self.get_premium_user(user_id)
        if not user:
            return False
        if user.get("expiry_time") and user["expiry_time"] < datetime.now():
            return False
        return True

    async def get_premium_user_rank(self, user_id):
        if await self.is_premium_user(user_id):
            user = await self.get_premium_user(user_id)
            return user["rank"]
        return "default"

    async def get_and_remove_expired_users(self):
        if not self._available:
            return []
        expired_users = []
        current_time = datetime.now()
        cursor = self.premium.find({"expiry_time": {"$ne": None, "$lt": current_time}})
        async for user in cursor:
            expired_users.append(user["user_id"])
        if expired_users:
            await self.premium.delete_many({"user_id": {"$in": expired_users}})
        return expired_users

    # ── Group / user authorization (/authorize, /unauthorize) ─────────────
    async def authorize_user(self, target_id, authorized_by):
        if not self._available:
            return True
        result = await self.authorized.update_one(
            {"id": int(target_id)},
            {"$set": {"authorized_by": int(authorized_by), "authorized_at": datetime.now()}},
            upsert=True,
        )
        return result.upserted_id is not None

    async def unauthorize_user(self, target_id):
        if not self._available:
            return False
        result = await self.authorized.delete_one({"id": int(target_id)})
        return result.deleted_count > 0

    async def is_authorized(self, target_id):
        if not self._available:
            # Without a DB, allow usage (permissive) so the bot still works.
            return True
        return bool(await self.authorized.find_one({"id": int(target_id)}))

    async def get_all_authorized(self):
        if not self._available:
            return []
        ids = []
        async for doc in self.authorized.find({}, {"id": 1, "_id": 0}):
            ids.append(doc["id"])
        return ids

    async def authorized_count(self):
        if not self._available:
            return 0
        return await self.authorized.count_documents({})

    # ── Per-user settings ─────────────────────────────────────────────────
    async def set_user_setting(self, user_id, key, value):
        if not self._available:
            return value
        await self.user_settings.update_one(
            {"user_id": int(user_id), "key": key},
            {"$set": {"value": value, "updated_at": datetime.now()}},
            upsert=True,
        )
        return value

    async def get_user_setting(self, user_id, key, default=None):
        if not self._available:
            return default
        doc = await self.user_settings.find_one({"user_id": int(user_id), "key": key})
        if not doc or "value" not in doc:
            return default
        return doc["value"]

    async def get_user_settings(self, user_id):
        settings = {}
        if not self._available:
            return settings
        cursor = self.user_settings.find({"user_id": int(user_id)})
        async for doc in cursor:
            if "value" in doc:
                settings[doc["key"]] = doc["value"]
        return settings

    async def reset_user_setting(self, user_id, key) -> bool:
        if not self._available:
            return False
        result = await self.user_settings.delete_one({"user_id": int(user_id), "key": key})
        return result.deleted_count > 0

    # ── Usage tracking ────────────────────────────────────────────────────
    async def check_and_update_usage(self, user_id, limit):
        if not self._available:
            return True  # permissive when DB absent
        user = await self.col.find_one({"id": int(user_id)})
        if not user:
            return False
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        usage_data = user.get("usage", {"date": today_str, "count": 0})
        if usage_data["date"] != today_str:
            usage_data = {"date": today_str, "count": 0}
        if usage_data["count"] >= limit:
            return False
        usage_data["count"] += 1
        await self.col.update_one({"id": int(user_id)}, {"$set": {"usage": usage_data}})
        return True


db = Database(Config.MONGO_URL, _DB_NAME)
