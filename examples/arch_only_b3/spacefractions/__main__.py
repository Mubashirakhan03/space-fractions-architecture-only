"""Support `python -m spacefractions` execution."""

from .ui import SpaceFractionsApp


def main() -> None:
    app = SpaceFractionsApp()
    app.start()


if __name__ == "__main__":
    main()
