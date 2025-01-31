from typing import Optional
from server import config
from server.database import Post

# Define the feed URI from config
uri = config.FEED_URI

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
