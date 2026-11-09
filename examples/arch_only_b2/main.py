"""Space Fractions - application entry point.

Run with: python main.py
"""

from spacefractions.ui.app import SpaceFractionsApp


def main() -> None:
    app = SpaceFractionsApp()
    app.run()


if __name__ == "__main__":
    main()
