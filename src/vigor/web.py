import argparse
import sys
from flask import Flask

app = Flask(__name__)


@app.get("/")
def index():
    return "<p style='font-family:system-ui;margin:3rem'>vigor is running.</p>"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vigor")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default="5006")
    args = ap.parse_args(argv)

    from waitress import serve
    print(f"{__name__}: http://{args.host}:{args.port}", file=sys.stderr)
    serve(app, host=args.host, port=args.port, threads=4)
    return 0