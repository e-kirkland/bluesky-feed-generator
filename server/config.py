import os
import logging

from dotenv import load_dotenv

from server.logger import logger

logger.setLevel(logging.INFO)

load_dotenv()

SERVICE_DID = os.environ.get('SERVICE_DID')
HOSTNAME = os.environ.get('HOSTNAME')
FLASK_RUN_FROM_CLI = os.environ.get('FLASK_RUN_FROM_CLI')

# Supabase configuration
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')

if FLASK_RUN_FROM_CLI:
    logger.setLevel(logging.DEBUG)

if HOSTNAME is None:
    raise RuntimeError('You should set "HOSTNAME" environment variable first.')

if SERVICE_DID is None:
    SERVICE_DID = f'did:web:{HOSTNAME}'

if SUPABASE_URL is None or SUPABASE_ANON_KEY is None:
    raise RuntimeError('Supabase configuration is missing. Please set SUPABASE_URL and SUPABASE_ANON_KEY')

FEED_URI = os.environ.get('FEED_URI')
if FEED_URI is None:
    raise RuntimeError('Publish your feed first (run publish_feed.py) to obtain Feed URI. '
                       'Set this URI to "FEED_URI" environment variable.')

# Update the database path to use the data directory
DATABASE_PATH = 'data/feed.db'  # This will resolve to /app/data/feed.db in the container
