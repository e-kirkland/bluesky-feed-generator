from collections import defaultdict
from datetime import datetime

from atproto import models

from server.logger import logger
from server.database import Post


def operations_callback(ops: defaultdict) -> None:
    # Here we can filter, process, run ML classification, etc.
    # After our feed alg we can save posts into our DB
    # Also, we should process deleted posts to remove them from our DB and keep it in sync

    # for example, let's create our custom feed that will contain all posts that contains alf related text

    posts_to_create = []
    
    # Log the total number of posts received only in debug mode
    created_posts = ops[models.ids.AppBskyFeedPost]['created']
    logger.debug(f"Processing {len(created_posts)} posts from firehose")
    
    for created_post in created_posts:
        author = created_post['author']
        record = created_post['record']
        
        text = record.text if hasattr(record, 'text') else ''

        # Check for TikTok posts
        if 'tiktok' in text.lower():
            inlined_text = text.replace('\n', ' ')
            logger.info(f"Found TikTok post from {author}: {inlined_text[:100]}...")
            
            reply_root = reply_parent = None
            if hasattr(record, 'reply'):
                reply = record.reply
                reply_root = reply.root.uri if hasattr(reply, 'root') else None
                reply_parent = reply.parent.uri if hasattr(reply, 'parent') else None

            post_data = {
                'uri': created_post['uri'],
                'cid': created_post['cid'],
                'reply_parent': reply_parent,
                'reply_root': reply_root
            }
            
            logger.debug(f"Creating post with data: {post_data}")
            posts_to_create.append(post_data)

    posts_to_delete = ops[models.ids.AppBskyFeedPost]['deleted']
    if posts_to_delete:
        post_uris_to_delete = [post['uri'] for post in posts_to_delete]
        logger.info(f"Deleting {len(post_uris_to_delete)} posts")
        Post.delete_many(post_uris_to_delete)

    if posts_to_create:
        logger.info(f"Storing {len(posts_to_create)} new TikTok posts")
        try:
            for post_dict in posts_to_create:
                Post.create(**post_dict)
        except Exception as e:
            logger.error(f'Error creating posts: {str(e)}')
            raise e
