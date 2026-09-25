"""Small CLI for the voice loop: ``python -m levi.voice <command>``."""

from __future__ import annotations

import argparse
import sys

from .listen import check_stt, record_and_transcribe, transcribe
from .speak import check_tts, speak


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="levi-voice", description="LEVI offline voice loop"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="report STT/TTS availability")

    p_listen = sub.add_parser("listen", help="transcribe an audio file")
    p_listen.add_argument("audio")
    p_listen.add_argument("--model")
    p_listen.add_argument("--timeout", type=int, default=120)

    p_record = sub.add_parser("record", help="record from the mic, then transcribe")
    p_record.add_argument("--seconds", type=int, default=5)
    p_record.add_argument("--model")

    p_speak = sub.add_parser("speak", help="speak text aloud")
    p_speak.add_argument("text")
    p_speak.add_argument("--voice")
    p_speak.add_argument("--engine", choices=("piper", "termux-tts-speak"))

    args = parser.parse_args(argv)

    if args.command == "status":
        stt = check_stt()
        tts = check_tts()
        print(f"stt: {stt.detail}")
        print(f"tts: {tts.detail}")
        return 0 if (stt.available or tts.available) else 1

    if args.command == "listen":
        result = transcribe(args.audio, model=args.model, timeout=args.timeout)
        if not result.ok:
            print(f"error: {result.error}", file=sys.stderr)
            return 1
        print(result.text)
        print(f"[engine: {result.engine}]", file=sys.stderr)
        return 0

    if args.command == "record":
        result = record_and_transcribe(args.seconds, model=args.model)
        if not result.ok:
            print(f"error: {result.error}", file=sys.stderr)
            return 1
        print(result.text)
        print(f"[engine: {result.engine}]", file=sys.stderr)
        return 0

    if args.command == "speak":
        result = speak(args.text, voice=args.voice, engine=args.engine)
        if not result.ok:
            print(f"error: {result.error}", file=sys.stderr)
            return 1
        print(result.detail)
        return 0

    return 2  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())
