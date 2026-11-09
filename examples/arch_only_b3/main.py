"""Entry point for the Space Fractions desktop application.

Run with: python main.py
"""

from spacefractions.ui import SpaceFractionsApp


def main() -> None:
    app = SpaceFractionsApp()
    app.start()


if __name__ == "__main__":
    main()
