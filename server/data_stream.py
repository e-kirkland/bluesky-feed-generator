import logging
from collections import defaultdict
import time
import threading
from typing import Callable, Optional

from atproto import Client, models
from atproto.firehose import FirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto.exceptions import FirehoseError

from server.database import SubscriptionState
from server.logger import logger

_INTERESTED_RECORDS = {
    models.AppBskyFeedLike: models.ids.AppBskyFeedLike,
    models.AppBskyFeedPost: models.ids.AppBskyFeedPost,
    models.AppBskyGraphFollow: models.ids.AppBskyGraphFollow,
}


def _get_ops_by_type(message: models.ComAtprotoSyncSubscribeRepos.Commit) -> dict:
    """Get operations from message grouped by type"""
    ops = {
        models.ids.AppBskyFeedPost: {
            'created': [],
            'deleted': []
        }
    }

    for op in message.ops:
        if not op.path.startswith('app.bsky.feed.post'):
            continue

        if op.action == 'create':
            if not isinstance(op.record, models.AppBskyFeedPost.Main):
                continue

            ops[models.ids.AppBskyFeedPost]['created'].append({
                'uri': f'at://{message.repo}/{op.path}',
                'cid': op.cid,
                'author': message.repo,
                'record': op.record
            })
        elif op.action == 'delete':
            ops[models.ids.AppBskyFeedPost]['deleted'].append({
                'uri': f'at://{message.repo}/{op.path}'
            })

    return ops


def _run(name: str, operations_callback: Callable, stream_stop_event: threading.Event) -> None:
    """Run firehose subscription"""
    client = FirehoseSubscribeReposClient()

    # Get or create subscription state
    state = SubscriptionState.get_or_create(name)
    cursor = state.cursor if state else 0

    def on_message_handler(message: models.ComAtprotoSyncSubscribeRepos.Commit) -> None:
        """Process message from firehose"""
        cursor = message.seq
        ops = _get_ops_by_type(message)

        try:
            operations_callback(ops)
        except Exception as e:
            logger.exception(f'Error in operations callback: {e}')

        # Update cursor in subscription state
        if state:
            state.update_cursor(cursor)

    def on_error_handler(e: FirehoseError) -> None:
        """Handle error from firehose"""
        logger.error(f'Firehose error: {e}')

    while not stream_stop_event.is_set():
        try:
            client.start(on_message_handler, on_error_handler, cursor=cursor)
        except Exception as e:
            logger.exception(f'Error in firehose client: {e}')
            time.sleep(1)


def run(name: str, operations_callback: Callable, stream_stop_event: threading.Event) -> None:
    """Run firehose subscription in a separate thread"""
    while not stream_stop_event.is_set():
        try:
            _run(name, operations_callback, stream_stop_event)
        except Exception as e:
            logger.exception(f'Error in firehose subscription: {e}')
            time.sleep(1)
