import logging
from collections import defaultdict

from atproto import AtUri, CAR, firehose_models, FirehoseSubscribeReposClient, models, parse_subscribe_repos_message
from atproto.exceptions import FirehoseError

from server.database import SubscriptionState
from server.logger import logger

_INTERESTED_RECORDS = {
    models.AppBskyFeedLike: models.ids.AppBskyFeedLike,
    models.AppBskyFeedPost: models.ids.AppBskyFeedPost,
    models.AppBskyGraphFollow: models.ids.AppBskyGraphFollow,
}


def _get_ops_by_type(commit: models.ComAtprotoSyncSubscribeRepos.Commit) -> defaultdict:
    """Get operations from message grouped by type"""
    operation_by_type = defaultdict(lambda: {'created': [], 'deleted': []})

    car = CAR.from_bytes(commit.blocks)
    for op in commit.ops:
        if op.action == 'update':
            continue

        uri = AtUri.from_str(f'at://{commit.repo}/{op.path}')

        if op.action == 'create':
            if not op.cid:
                continue

            create_info = {'uri': str(uri), 'cid': str(op.cid), 'author': commit.repo}

            record_raw_data = car.blocks.get(op.cid)
            if not record_raw_data:
                continue

            record = models.get_or_create(record_raw_data, strict=False)
            if record is None:
                continue

            for record_type, record_nsid in _INTERESTED_RECORDS.items():
                if uri.collection == record_nsid and models.is_record_type(record, record_type):
                    operation_by_type[record_nsid]['created'].append({'record': record, **create_info})
                    break

        if op.action == 'delete':
            operation_by_type[uri.collection]['deleted'].append({'uri': str(uri)})

    return operation_by_type


def run(name, operations_callback, stream_stop_event=None):
    while stream_stop_event is None or not stream_stop_event.is_set():
        try:
            _run(name, operations_callback, stream_stop_event)
        except FirehoseError as e:
            if logger.level == logging.DEBUG:
                raise e
            logger.error(f'Firehose error: {e}. Reconnecting to the firehose.')


def _run(name, operations_callback, stream_stop_event=None):
    state = SubscriptionState.get_or_create(name)

    params = None
    if state:
        params = models.ComAtprotoSyncSubscribeRepos.Params(cursor=state.cursor)

    client = FirehoseSubscribeReposClient(params)

    def on_message_handler(message: firehose_models.MessageFrame) -> None:
        if stream_stop_event and stream_stop_event.is_set():
            client.stop()
            return

        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return

        if commit.seq % 1000 == 0:
            logger.debug(f'Updated cursor to {commit.seq}')
            client.update_params(models.ComAtprotoSyncSubscribeRepos.Params(cursor=commit.seq))
            if state:
                state.update_cursor(commit.seq)

        if not commit.blocks:
            return

        operations_callback(_get_ops_by_type(commit))

    client.start(on_message_handler)