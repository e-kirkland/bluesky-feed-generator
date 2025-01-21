from datetime import datetime
import os
from peewee import *
from server.config import DATABASE_PATH

# Ensure the data directory exists
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# Create the database connection
db = SqliteDatabase(DATABASE_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class Post(BaseModel):
    uri = CharField(index=True)
    cid = CharField()
    reply_parent = CharField(null=True, default=None)
    reply_root = CharField(null=True, default=None)
    indexed_at = DateTimeField(default=datetime.utcnow)


class SubscriptionState(BaseModel):
    service = CharField(unique=True)
    cursor = BigIntegerField()


if db.is_closed():
    db.connect()
    db.create_tables([Post, SubscriptionState])
