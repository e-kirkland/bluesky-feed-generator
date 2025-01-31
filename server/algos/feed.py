from typing import Optional
from server.database import Post

def handler(cursor: Optional[str], limit: int) -> dict:
    """Handle feed generation"""
    posts = Post.get_recent(limit=limit, cursor=cursor)
    
    feed = []
    cursor = None
    
    for post in posts:
        feed.append({
            'post': post.uri
        })
        cursor = post.indexed_at.isoformat()

    return {
        'cursor': cursor,
        'feed': feed
    }
