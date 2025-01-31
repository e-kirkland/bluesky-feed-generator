import logging
import json
import asyncio
import websockets
from collections import defaultdict
import time
import threading
from typing import Callable, Optional
import cbor2

from atproto import Client, models
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


async def _websocket_client(name: str, operations_callback: Callable, stream_stop_event: threading.Event):
    """Websocket client for firehose subscription"""
    uri = "wss://bsky.network/xrpc/com.atproto.sync.subscribeRepos"
    
    state = SubscriptionState.get_or_create(name)
    cursor = state.cursor if state else 0

    while not stream_stop_event.is_set():
        try:
            async with websockets.connect(uri) as websocket:
                if cursor:
                    await websocket.send(json.dumps({"cursor": cursor}))

                while not stream_stop_event.is_set():
                    message = await websocket.recv()
                    try:
                        # Try parsing as JSON first
                        if isinstance(message, str):
                            data = json.loads(message)
                        # If it's bytes, try CBOR decoding
                        else:
                            data = cbor2.loads(message)
                        
                        if '#commit' in data:
                            commit_data = data['#commit']
                            cursor = commit_data.get('seq')
                            ops = _get_ops_by_type(models.ComAtprotoSyncSubscribeRepos.Commit(**commit_data))

                            try:
                                operations_callback(ops)
                            except Exception as e:
                                logger.exception(f'Error in operations callback: {e}')

                            if state and cursor:
                                state.update_cursor(cursor)
                    except Exception as e:
                        logger.exception(f'Error processing message: {e}')
                        continue

        except Exception as e:
            logger.exception(f'Websocket error: {e}')
            if not stream_stop_event.is_set():
                await asyncio.sleep(1)


def _run(name: str, operations_callback: Callable, stream_stop_event: threading.Event) -> None:
    """Run firehose subscription"""
    asyncio.run(_websocket_client(name, operations_callback, stream_stop_event))


def run(name: str, operations_callback: Callable, stream_stop_event: threading.Event) -> None:
    """Run firehose subscription in a separate thread"""
    while not stream_stop_event.is_set():
        try:
            _run(name, operations_callback, stream_stop_event)
        except Exception as e:
            logger.exception(f'Error in firehose subscription: {e}')
            time.sleep(1)
