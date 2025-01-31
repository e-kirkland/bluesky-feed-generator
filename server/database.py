from datetime import datetime
from typing import List, Optional
from supabase import create_client, Client
from server.config import SUPABASE_URL, SUPABASE_ANON_KEY

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
        supabase.table('posts').insert(data).execute()
        return post

    @staticmethod
    def delete_many(uris: List[str]) -> None:
        supabase.table('posts').delete().in_('uri', uris).execute()

    @staticmethod
    def get_recent(limit: int = 20, cursor: Optional[str] = None) -> List['Post']:
        query = supabase.table('posts').select('*').order('indexed_at', desc=True)
        
        if cursor:
            query = query.lt('indexed_at', cursor)
        
        result = query.limit(limit).execute()
        
        return [
            Post(
                uri=row['uri'],
                cid=row['cid'],
                reply_parent=row['reply_parent'],
                reply_root=row['reply_root'],
                indexed_at=datetime.fromisoformat(row['indexed_at'])
            )
            for row in result.data
        ]

class SubscriptionState:
    def __init__(self, service: str, cursor: int):
        self.service = service
        self.cursor = cursor

    @staticmethod
    def get_or_create(service: str) -> 'SubscriptionState':
        result = supabase.table('subscription_states').select('*').eq('service', service).execute()
        
        if result.data:
            return SubscriptionState(service=result.data[0]['service'], 
                                   cursor=result.data[0]['cursor'])
        
        state = SubscriptionState(service=service, cursor=0)
        supabase.table('subscription_states').insert({
            'service': state.service,
            'cursor': state.cursor
        }).execute()
        
        return state

    def update_cursor(self, new_cursor: int) -> None:
        supabase.table('subscription_states').update({
            'cursor': new_cursor
        }).eq('service', self.service).execute()
