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
