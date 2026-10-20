"""Local server entry point; select a psycopg-compatible loop before startup."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.asyncio_compat import configure_event_loop_policy
configure_event_loop_policy()
import uvicorn

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run('app.main:app', host='127.0.0.1', port=args.port, loop='asyncio', access_log=False)
