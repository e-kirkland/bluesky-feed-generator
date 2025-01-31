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
    for created_post in ops[models.ids.AppBskyFeedPost]['created']:
        author = created_post['author']
        record = created_post['record']

        # print all texts just as demo that data stream works
        post_with_images = isinstance(record.embed, models.AppBskyEmbedImages.Main)
        inlined_text = record.text.replace('\n', ' ')
        # logger.debug(
        #     f'NEW POST '
        #     f'[CREATED_AT={record.created_at}]'
        #     f'[AUTHOR={author}]'
        #     f'[WITH_IMAGE={post_with_images}]'
        #     f': {inlined_text}'
        # )

        # only tiktok-related posts
        if 'tiktok' in record.text.lower():
            reply_root = reply_parent = None
            if record.reply:
                reply_root = record.reply.root.uri
                reply_parent = record.reply.parent.uri

            posts_to_create.append({
                'uri': created_post['uri'],
                'cid': created_post['cid'],
                'reply_parent': reply_parent,
                'reply_root': reply_root
            })

    posts_to_delete = ops[models.ids.AppBskyFeedPost]['deleted']
    if posts_to_delete:
        post_uris_to_delete = [post['uri'] for post in posts_to_delete]
        Post.delete_many(post_uris_to_delete)
        logger.debug(f'Deleted from feed: {len(post_uris_to_delete)}')

    if posts_to_create:
        try:
            for post_dict in posts_to_create:
                Post.create(**post_dict)
            logger.debug(f'Added to feed: {len(posts_to_create)}')
        except Exception as e:
            logger.error(f'Error creating posts: {str(e)}')
            raise e
