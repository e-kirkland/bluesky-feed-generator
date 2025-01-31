from datetime import datetime
from typing import List, Optional
from supabase import create_client, Client
from server.config import SUPABASE_URL, SUPABASE_ANON_KEY
from server.logger import logger
import re

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

class Post:
    def __init__(self, uri: str, cid: str, reply_parent: Optional[str] = None, 
                 reply_root: Optional[str] = None, indexed_at: datetime = None):
        self.uri = uri
        self.cid = cid
        self.reply_parent = reply_parent
        self.reply_root = reply_root
        self.indexed_at = indexed_at or datetime.utcnow()

    @staticmethod
    def create(uri: str, cid: str, reply_parent: Optional[str] = None, 
               reply_root: Optional[str] = None) -> 'Post':
        post = Post(uri, cid, reply_parent, reply_root)
        data = {
            'uri': post.uri,
            'cid': post.cid,
            'reply_parent': post.reply_parent,
            'reply_root': post.reply_root,
            'indexed_at': post.indexed_at.isoformat()
        }
        try:
            logger.info(f"Attempting to insert post: {data['uri']}")
            logger.debug(f"Post data: {data}")
            result = supabase.table('posts').insert(data).execute()
            logger.debug(f"Supabase response: {result}")
            logger.info(f"Successfully inserted post: {data['uri']}")
            return post
        except Exception as e:
            logger.error(f"Error inserting post {data['uri']}: {str(e)}")
            raise

    @staticmethod
    def delete_many(uris: List[str]) -> None:
        try:
            logger.info(f"Attempting to delete posts: {uris}")
            result = supabase.table('posts').delete().in_('uri', uris).execute()
            logger.info(f"Successfully deleted {len(uris)} posts")
        except Exception as e:
            logger.error(f"Error deleting posts: {str(e)}")
            raise

    @staticmethod
    def get_recent(limit: int = 20, cursor: Optional[str] = None) -> List['Post']:
        try:
            logger.info(f"Getting recent posts (limit={limit}, cursor={cursor})")
            query = supabase.table('posts').select('*').order('indexed_at', desc=True)
            
            if cursor:
                query = query.lt('indexed_at', cursor)
            
            result = query.limit(limit).execute()
            logger.info(f"Found {len(result.data)} posts")
            
            def parse_datetime(dt_str: str) -> datetime:
                # Remove microseconds if present (everything between . and +/Z)
                dt_str = re.sub(r'\.\d+(?=[-+Z])', '', dt_str)
                # Remove timezone offset if present
                dt_str = re.sub(r'[-+]\d{2}:?\d{2}$', '', dt_str)
                # Remove Z if present
                dt_str = dt_str.replace('Z', '')
                return datetime.fromisoformat(dt_str)
            
            return [
                Post(
                    uri=row['uri'],
                    cid=row['cid'],
                    reply_parent=row['reply_parent'],
                    reply_root=row['reply_root'],
                    indexed_at=parse_datetime(row['indexed_at'])
                )
                for row in result.data
            ]
        except Exception as e:
            logger.error(f"Error getting recent posts: {str(e)}")
            raise

class SubscriptionState:
    def __init__(self, service: str, cursor: int):
        self.service = service
        self.cursor = cursor

    @staticmethod
    def get_or_create(service: str) -> 'SubscriptionState':
        try:
            logger.info(f"Attempting to get/create subscription state for service: {service}")
            result = supabase.table('subscription_states').select('*').eq('service', service).execute()
            
            if result.data:
                logger.info(f"Found existing subscription state for service: {service}")
                return SubscriptionState(service=result.data[0]['service'], 
                                       cursor=result.data[0]['cursor'])
            
            logger.info(f"Creating new subscription state for service: {service}")
            state = SubscriptionState(service=service, cursor=0)
            supabase.table('subscription_states').insert({
                'service': state.service,
                'cursor': state.cursor
            }).execute()
            
            return state
        except Exception as e:
            logger.error(f"Error in get_or_create for service {service}: {str(e)}")
            raise

    def update_cursor(self, new_cursor: int) -> None:
        try:
            logger.info(f"Updating cursor for service {self.service} to {new_cursor}")
            result = supabase.table('subscription_states').update({
                'cursor': new_cursor
            }).eq('service', self.service).execute()
            logger.info(f"Successfully updated cursor for service {self.service}")
        except Exception as e:
            logger.error(f"Error updating cursor for service {self.service}: {str(e)}")
            raise

class User:
    def __init__(self, did: str, added_at: datetime = None, active: bool = True):
        self.did = did
        self.added_at = added_at or datetime.utcnow()
        self.active = active

    @staticmethod
    def add(did: str) -> 'User':
        """Add a new user or reactivate an existing one"""
        try:
            logger.info(f"Adding user to feed: {did}")
            data = {
                'did': did,
                'added_at': datetime.utcnow().isoformat(),
                'active': True
            }
            
            # Try to update existing user first
            result = supabase.table('users').update(data).eq('did', did).execute()
            
            # If no user was updated, insert new one
            if not result.data:
                result = supabase.table('users').insert(data).execute()
            
            logger.info(f"Successfully added user: {did}")
            return User(did=did)
        except Exception as e:
            logger.error(f"Error adding user {did}: {str(e)}")
            raise

    @staticmethod
    def remove(did: str) -> None:
        """Deactivate a user and remove their posts"""
        try:
            logger.info(f"Removing user from feed: {did}")
            
            # Deactivate user
            result = supabase.table('users').update({
                'active': False
            }).eq('did', did).execute()
            
            # Remove their posts
            posts = supabase.table('posts').select('uri').eq('author', did).execute()
            if posts.data:
                uris = [post['uri'] for post in posts.data]
                Post.delete_many(uris)
            
            logger.info(f"Successfully removed user and their posts: {did}")
        except Exception as e:
            logger.error(f"Error removing user {did}: {str(e)}")
            raise

    @staticmethod
    def is_active(did: str) -> bool:
        """Check if a user is active"""
        try:
            result = supabase.table('users').select('active').eq('did', did).execute()
            return bool(result.data and result.data[0]['active'])
        except Exception as e:
            logger.error(f"Error checking user status for {did}: {str(e)}")
            raise

    @staticmethod
    def get_all_active() -> List[str]:
        """Get all active users"""
        try:
            logger.debug("Getting all active users")
            result = supabase.table('users').select('did').eq('active', True).execute()
            return [row['did'] for row in result.data]
        except Exception as e:
            logger.error(f"Error getting active users: {str(e)}")
            raise
