import argparse


def setup_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument("--host", type=str, default="0.0.0.0", help="server host")
    parser.add_argument("--port", type=int, default=11636, help="server port")

    return parser
