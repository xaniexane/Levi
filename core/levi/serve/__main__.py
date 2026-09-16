"""``python -m levi.serve`` — serve a static directory over HTTP."""

from .server import build_parser, serve_forever


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return serve_forever(directory=args.dir, port=args.port, bind=args.bind)


if __name__ == "__main__":
    raise SystemExit(main())
