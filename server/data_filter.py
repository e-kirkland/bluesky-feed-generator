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
    
    # Log the total number of posts received
    created_posts = ops[models.ids.AppBskyFeedPost]['created']
    logger.info(f"Received {len(created_posts)} posts from firehose")
    
    for created_post in created_posts:
        author = created_post['author']
        record = created_post['record']

        # Log all posts for debugging
        post_with_images = record.get('embed', {}).get('$type') == 'app.bsky.embed.images'
        text = record.get('text', '')
        inlined_text = text.replace('\n', ' ')
        logger.debug(
            f'NEW POST '
            f'[AUTHOR={author}]'
            f'[WITH_IMAGE={post_with_images}]'
            f': {inlined_text}'
        )

        # Check for TikTok posts
        if 'tiktok' in text.lower():
            logger.info(f"Found TikTok post from {author}: {inlined_text[:100]}...")
            reply_root = reply_parent = None
            
            # Handle reply data
            reply = record.get('reply')
            if reply:
                reply_root = reply.get('root', {}).get('uri')
                reply_parent = reply.get('parent', {}).get('uri')

            post_data = {
                'uri': created_post['uri'],
                'cid': created_post['cid'],
                'reply_parent': reply_parent,
                'reply_root': reply_root
            }
            
            logger.debug(f"Creating post with data: {post_data}")
            posts_to_create.append(post_data)
        else:
            logger.debug(f"Skipping non-TikTok post: {inlined_text[:100]}...")

    posts_to_delete = ops[models.ids.AppBskyFeedPost]['deleted']
    if posts_to_delete:
        post_uris_to_delete = [post['uri'] for post in posts_to_delete]
        logger.info(f"Attempting to delete posts: {post_uris_to_delete}")
        Post.delete_many(post_uris_to_delete)
        logger.debug(f'Deleted from feed: {len(post_uris_to_delete)}')

    if posts_to_create:
        logger.info(f"Attempting to create {len(posts_to_create)} posts")
        try:
            for post_dict in posts_to_create:
                Post.create(**post_dict)
            logger.debug(f'Added to feed: {len(posts_to_create)}')
        except Exception as e:
            logger.error(f'Error creating posts: {str(e)}')
            raise e
