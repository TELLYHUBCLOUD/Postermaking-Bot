import motor.motor_asyncio
from config import Config
from datetime import datetime
import logging

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.premium = self.db.premium_users
        self.authorized = self.db.authorized_users
        self.user_settings = self.db.user_settings

    def new_user(self, id):
        return dict(
            id=id
        )

    async def add_user(self, id):
        try:
            user = await self.col.find_one({'id': int(id)})
            if not user:
                user = self.new_user(id)
                await self.col.insert_one(user)
                return True
        except Exception as e:
            logging.error(f"DB Error in add_user: {e}")
        return False

    async def is_user_exist(self, id):
        try:
            user = await self.col.find_one({'id': int(id)})
            return True if user else False
        except Exception as e:
             logging.error(f"DB Error in is_user_exist: {e}")
             return False

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    # Premium Methods
    async def add_premium_user(self, user_id, rank, expiry_time):
        await self.premium.update_one(
            {'user_id': user_id},
            {'$set': {'rank': rank, 'expiry_time': expiry_time}},
            upsert=True
        )

    async def remove_premium_user(self, user_id):
        await self.premium.delete_one({'user_id': user_id})

    async def get_premium_user(self, user_id):
        return await self.premium.find_one({'user_id': user_id})

    async def is_premium_user(self, user_id):
        user = await self.get_premium_user(user_id)
        if not user:
            return False
        if user.get('expiry_time') and user['expiry_time'] < datetime.now():
            return False
        return True

    async def get_premium_user_rank(self, user_id):
        if await self.is_premium_user(user_id):
            user = await self.get_premium_user(user_id)
            return user['rank']
        return "default"

    async def get_and_remove_expired_users(self):
        expired_users = []
        current_time = datetime.now()
        cursor = self.premium.find({"expiry_time": {"$ne": None, "$lt": current_time}})
        async for user in cursor:
            expired_users.append(user['user_id'])
        
        if expired_users:
            await self.premium.delete_many({"user_id": {"$in": expired_users}})
            
        return expired_users

    # ── Group / User Authorization (for /authorize and /unauthorize) ───
    async def authorize_user(self, target_id, authorized_by):
        """Grant bot usage to a user or group chat. Returns True if newly added."""
        result = await self.authorized.update_one(
            {"id": int(target_id)},
            {"$set": {"authorized_by": int(authorized_by), "authorized_at": datetime.now()}},
            upsert=True,
        )
        return result.upserted_id is not None

    async def unauthorize_user(self, target_id):
        """Revoke bot usage from a user or group chat. Returns True if removed."""
        result = await self.authorized.delete_one({"id": int(target_id)})
        return result.deleted_count > 0

    async def is_authorized(self, target_id):
        """Check whether a user/group is currently authorized."""
        doc = await self.authorized.find_one({"id": int(target_id)})
        return True if doc else False

    async def get_all_authorized(self):
        """Return a list of authorized target ids."""
        ids = []
        async for doc in self.authorized.find({}, {"id": 1, "_id": 0}):
            ids.append(doc["id"])
        return ids

    async def authorized_count(self):
        return await self.authorized.count_documents({})

    # ── Per-user settings (e.g. custom thumbnail brand) ───────────────────
    # Settings are stored as one document per user:
    #   { "_id": ..., "user_id": <id>, "thumbnail_brand": "...", "updated_at": ... }

    async def set_user_setting(self, user_id, key: str, value):
        """Save a single user setting (upsert). Returns the value stored."""
        # Keep the setting document slim: only one key/value pair per doc,
        # keyed by (user_id, key).
        await self.user_settings.update_one(
            {"user_id": int(user_id), "key": key},
            {"$set": {"value": value, "updated_at": datetime.now()}},
            upsert=True,
        )
        return value

    async def get_user_setting(self, user_id, key: str, default=None):
        """Fetch a single user setting, returning ``default`` if not set."""
        doc = await self.user_settings.find_one({"user_id": int(user_id), "key": key})
        if not doc or "value" not in doc:
            return default
        return doc["value"]

    async def get_user_settings(self, user_id):
        """Fetch all settings for a user as a dict {key: value}."""
        settings = {}
        cursor = self.user_settings.find({"user_id": int(user_id)})
        async for doc in cursor:
            if "value" in doc:
                settings[doc["key"]] = doc["value"]
        return settings

    async def reset_user_setting(self, user_id, key: str) -> bool:
        """Delete a single user setting. Returns True if removed."""
        result = await self.user_settings.delete_one({"user_id": int(user_id), "key": key})
        return result.deleted_count > 0

    # Usage Tracking
    async def check_and_update_usage(self, user_id, limit):
        user = await self.col.find_one({'id': int(user_id)})
        if not user:
            return False # Should theoretically exist
            
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        usage_data = user.get('usage', {'date': today_str, 'count': 0})
        
        # Reset if different day
        if usage_data['date'] != today_str:
            usage_data = {'date': today_str, 'count': 0}
            
        # Check limit
        if usage_data['count'] >= limit:
            return False
            
        # Increment
        usage_data['count'] += 1
        await self.col.update_one({'id': int(user_id)}, {'$set': {'usage': usage_data}})
        return True


db = Database(Config.MONGO_URL, "PosterBot")
