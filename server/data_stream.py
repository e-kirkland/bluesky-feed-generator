import logging
import time
import threading
from collections import defaultdict
from typing import Callable, Optional

from atproto import Client, models
from atproto.exceptions import FirehoseError
from atproto.firehose import parse_subscribe_repos_message
from atproto.xrpc_client.websocket import WebsocketClient

from server.database import SubscriptionState
from server.logger import logger

_INTERESTED_RECORDS = {
    models.AppBskyFeedPost: models.ids.AppBskyFeedPost,
}

def _get_ops_by_type(commit) -> defaultdict:
    """Get operations from message grouped by type"""
    operation_by_type = defaultdict(lambda: {'created': [], 'deleted': []})

    for op in commit.ops:
        if op.action == 'update':
            continue

        if op.action == 'create':
            if not op.record or not isinstance(op.record, models.AppBskyFeedPost.Main):
                continue

            create_info = {
                'uri': f'at://{commit.repo}/{op.path}',
                'cid': str(op.cid),
                'author': commit.repo,
                'record': op.record
            }
            operation_by_type[models.ids.AppBskyFeedPost]['created'].append(create_info)

        elif op.action == 'delete':
            operation_by_type[models.ids.AppBskyFeedPost]['deleted'].append({
                'uri': f'at://{commit.repo}/{op.path}'
            })

    return operation_by_type

def _run(name: str, operations_callback: Callable, stream_stop_event: threading.Event) -> None:
    """Run firehose subscription"""
    logger.info("Starting firehose connection...")
    
    state = SubscriptionState.get_or_create(name)
    cursor = state.cursor if state else None

    client = WebsocketClient("wss://bsky.network/xrpc/com.atproto.sync.subscribeRepos")

    def on_message_handler(message) -> None:
        """Process message from firehose"""
        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return

        # Update cursor periodically
        if commit.seq % 1000 == 0:
            logger.debug(f'Updated cursor for {name} to {commit.seq}')
            if state:
                state.update_cursor(commit.seq)

        ops = _get_ops_by_type(commit)
        try:
            operations_callback(ops)
        except Exception as e:
            logger.exception(f'Error in operations callback: {e}')

    def on_error_handler(e: Exception) -> None:
        """Handle error from firehose"""
        logger.error(f'Firehose error: {e}')

    while not stream_stop_event.is_set():
        try:
            client.subscribe(on_message_handler, on_error_handler, cursor=cursor)
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
