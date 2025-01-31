import sys
import signal
import threading

from server import config
from server import data_stream

from flask import Flask, jsonify, request

from server.algos import algos
from server.data_filter import operations_callback
from server.database import User

app = Flask(__name__)

stream_stop_event = threading.Event()
stream_thread = threading.Thread(
    target=data_stream.run, args=(config.SERVICE_DID, operations_callback, stream_stop_event,)
)
stream_thread.start()


def sigint_handler(*_):
    print('Stopping data stream...')
    stream_stop_event.set()
    sys.exit(0)


signal.signal(signal.SIGINT, sigint_handler)


@app.route('/')
def index():
    return 'ATProto Feed Generator powered by The AT Protocol SDK for Python (https://github.com/MarshalX/atproto).'


@app.route('/.well-known/did.json', methods=['GET'])
def did_json():
    app.logger.debug(f"SERVICE_DID: {config.SERVICE_DID}")
    app.logger.debug(f"HOSTNAME: {config.HOSTNAME}")
    app.logger.debug(f"Condition: {config.SERVICE_DID.endswith(config.HOSTNAME)}")
    
    if not config.SERVICE_DID.endswith(config.HOSTNAME):
        app.logger.warning(f"404 because SERVICE_DID ({config.SERVICE_DID}) doesn't end with HOSTNAME ({config.HOSTNAME})")
        return '', 404

    return jsonify({
        '@context': ['https://www.w3.org/ns/did/v1'],
        'id': config.SERVICE_DID,
        'service': [
            {
                'id': '#bsky_fg',
                'type': 'BskyFeedGenerator',
                'serviceEndpoint': f'https://{config.HOSTNAME}'
            }
        ]
    })


@app.route('/xrpc/app.bsky.feed.describeFeedGenerator', methods=['GET'])
def describe_feed_generator():
    feeds = [{'uri': uri} for uri in algos.keys()]
    response = {
        'encoding': 'application/json',
        'body': {
            'did': config.SERVICE_DID,
            'feeds': feeds
        }
    }
    return jsonify(response)


@app.route('/xrpc/app.bsky.feed.getFeedSkeleton', methods=['GET'])
def get_feed_skeleton():
    feed = request.args.get('feed', default=None, type=str)
    algo = algos.get(feed)
    if not algo:
        return 'Unsupported algorithm', 400

    # Example of how to check auth if giving user-specific results:
    """
    from server.auth import AuthorizationError, validate_auth
    try:
        requester_did = validate_auth(request)
    except AuthorizationError:
        return 'Unauthorized', 401
    """

    try:
        cursor = request.args.get('cursor', default=None, type=str)
        limit = request.args.get('limit', default=20, type=int)
        body = algo(cursor, limit)
    except ValueError:
        return 'Malformed cursor', 400

    return jsonify(body)


@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200


@app.route('/api/users', methods=['POST'])
def add_user():
    """Add a user to the feed"""
    try:
        data = request.get_json()
        if not data or 'did' not in data:
            return jsonify({'error': 'Missing did in request'}), 400
        
        did = data['did']
        User.add(did)
        return jsonify({'message': f'Successfully added user: {did}'}), 200
    except Exception as e:
        app.logger.error(f"Error adding user: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/users/<did>', methods=['DELETE'])
def remove_user(did):
    """Remove a user from the feed"""
    try:
        if not User.is_active(did):
            return jsonify({'message': 'User not found or already inactive'}), 404
        
        User.remove(did)
        return jsonify({'message': f'Successfully removed user: {did}'}), 200
    except Exception as e:
        app.logger.error(f"Error removing user: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/users', methods=['GET'])
def list_users():
    """List all active users"""
    try:
        users = User.get_all_active()
        return jsonify({'users': users}), 200
    except Exception as e:
        app.logger.error(f"Error listing users: {str(e)}")
        return jsonify({'error': str(e)}), 500
