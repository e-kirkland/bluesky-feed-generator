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
    logger.debug(f"Processing message with {len(message.ops)} operations")
    
    ops = {
        models.ids.AppBskyFeedPost: {
            'created': [],
            'deleted': []
        }
    }

    for op in message.ops:
        logger.debug(f"Processing operation: path={op.get('path')}, action={op.get('action')}")
        
        path = op.get('path', '')
        if not path.startswith('app.bsky.feed.post'):
            logger.debug(f"Skipping non-post operation: {path}")
            continue

        action = op.get('action')
        if action == 'create':
            record = op.get('record')
            if not record:
                logger.debug("No record in create operation")
                continue

            logger.debug(f"Found post: repo={message.repo}, path={path}")
            ops[models.ids.AppBskyFeedPost]['created'].append({
                'uri': f'at://{message.repo}/{path}',
                'cid': op.get('cid'),
                'author': message.repo,
                'record': record
            })
        elif action == 'delete':
            logger.debug(f"Found deleted post: repo={message.repo}, path={path}")
            ops[models.ids.AppBskyFeedPost]['deleted'].append({
                'uri': f'at://{message.repo}/{path}'
            })

    logger.debug(f"Processed message: found {len(ops[models.ids.AppBskyFeedPost]['created'])} created posts and {len(ops[models.ids.AppBskyFeedPost]['deleted'])} deleted posts")
    return ops


async def _websocket_client(name: str, operations_callback: Callable, stream_stop_event: threading.Event):
    """Websocket client for firehose subscription"""
    uri = "wss://bsky.network/xrpc/com.atproto.sync.subscribeRepos"
    
    logger.info("Starting firehose connection...")
    
    state = SubscriptionState.get_or_create(name)
    cursor = state.cursor if state else 0

    while not stream_stop_event.is_set():
        try:
            logger.info(f"Connecting to firehose with cursor: {cursor}")
            async with websockets.connect(uri) as websocket:
                if cursor:
                    await websocket.send(json.dumps({"cursor": cursor}))
                logger.info("Successfully connected to firehose")

                while not stream_stop_event.is_set():
                    message = await websocket.recv()
                    logger.debug(f"Received message type: {type(message)}")
                    try:
                        # Try parsing as JSON first
                        if isinstance(message, str):
                            logger.debug("Parsing message as JSON")
                            data = json.loads(message)
                        # If it's bytes, try CBOR decoding
                        else:
                            logger.debug("Parsing message as CBOR")
                            data = cbor2.loads(message)
                        
                        # Handle different message types
                        if 't' in data:
                            message_type = data.get('t')
                            logger.debug(f"Message type: {message_type}")
                            
                            if message_type == '#commit':
                                logger.debug("Processing commit message")
                                if 'ops' in data:
                                    ops = _get_ops_by_type(models.ComAtprotoSyncSubscribeRepos.Commit(
                                        seq=data.get('seq', 0),
                                        repo=data.get('repo', ''),
                                        ops=data.get('ops', []),
                                        time=data.get('time', ''),
                                        blobs=data.get('blocks', [])
                                    ))
                                    try:
                                        operations_callback(ops)
                                    except Exception as e:
                                        logger.exception(f'Error in operations callback: {e}')

                                    if state and data.get('seq'):
                                        state.update_cursor(data['seq'])
                            else:
                                logger.debug(f"Skipping message type: {message_type}")
                        else:
                            logger.debug(f"Message does not contain type. Keys: {data.keys()}")
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
