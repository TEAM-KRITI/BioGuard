#This code was published by @MightyAyush on github.com/mightyayush
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import logging

class Database:
    def __init__(self, uri: str, db_name: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        self.users = self.db["users"]
        self.groups = self.db["groups"]
        logging.info("Connected to MongoDB successfully.")

    async def add_user(self, user_id: int, username: str = None):
        await self.users.update_one(
            {"user_id": user_id},
            {
                "$set": {"username": username, "last_seen": datetime.utcnow()},
                "$setOnInsert": {"date_joined": datetime.utcnow()}
            },
            upsert=True
        )

    async def get_all_user_ids(self) -> list[int]:
        cursor = self.users.find({}, {"user_id": 1})
        docs = await cursor.to_list(length=None)
        return [doc["user_id"] for doc in docs if "user_id" in doc]

    async def add_group(self, chat_id: int, title: str = None):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {
                "$set": {"title": title, "last_active": datetime.utcnow()},
                "$setOnInsert": {
                    "punishment_mode": "mute",
                    "approved_users": [],
                    "date_added": datetime.utcnow()
                }
            },
            upsert=True
        )

    async def get_group_config(self, chat_id: int) -> str:
        doc = await self.groups.find_one({"chat_id": chat_id}, {"punishment_mode": 1})
        if doc and "punishment_mode" in doc:
            return doc["punishment_mode"]
        return "mute"

    async def set_group_config(self, chat_id: int, mode: str):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {"punishment_mode": mode}},
            upsert=True
        )

    async def get_approved_users(self, chat_id: int) -> list[int]:
        doc = await self.groups.find_one({"chat_id": chat_id}, {"approved_users": 1})
        if doc and "approved_users" in doc:
            return doc["approved_users"]
        return []

    async def approve_user(self, chat_id: int, user_id: int):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$addToSet": {"approved_users": user_id}},
            upsert=True
        )

    async def unapprove_user(self, chat_id: int, user_id: int):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$pull": {"approved_users": user_id}},
            upsert=True
        )

    async def unapprove_all(self, chat_id: int):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {"approved_users": []}},
            upsert=True
        )


    async def get_paidgirl_config(self, chat_id: int) -> dict:
        doc = await self.groups.find_one(
            {"chat_id": chat_id},
            {"paidgirl_guard": 1, "paidgirl_allowed": 1}
        )
        if not doc:
            return {"enabled": False, "allowed_users": []}
        return {
            "enabled": bool(doc.get("paidgirl_guard", False)),
            "allowed_users": [int(uid) for uid in doc.get("paidgirl_allowed", [])],
        }

    async def set_paidgirl_guard(self, chat_id: int, enabled: bool):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {"paidgirl_guard": bool(enabled)}},
            upsert=True
        )

    async def paidgirl_allow_user(self, chat_id: int, user_id: int):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$addToSet": {"paidgirl_allowed": int(user_id)}},
            upsert=True
        )

    async def paidgirl_unallow_user(self, chat_id: int, user_id: int):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$pull": {"paidgirl_allowed": int(user_id)}},
            upsert=True
        )

    async def paidgirl_clear_allowed(self, chat_id: int):
        await self.groups.update_one(
            {"chat_id": chat_id},
            {"$set": {"paidgirl_allowed": []}},
            upsert=True
        )

    async def get_all_group_ids(self) -> list[int]:
        cursor = self.groups.find({}, {"chat_id": 1})
        docs = await cursor.to_list(length=None)
        return [doc["chat_id"] for doc in docs if "chat_id" in doc]

    async def get_stats(self) -> tuple[int, int]:
        users_count = await self.users.count_documents({})
        groups_count = await self.groups.count_documents({})
        return users_count, groups_count
