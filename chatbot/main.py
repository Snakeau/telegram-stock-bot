"""Compatibility entry point that delegates to the unified root runner."""

from bot import main as root_main


def run() -> None:
    """Run application using the single supported lifecycle in bot.py."""
    root_main()


if __name__ == "__main__":
    run()
