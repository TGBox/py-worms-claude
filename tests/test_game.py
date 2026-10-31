import os
import unittest

# Ensure headless execution in CI environments
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["ARCADE_HEADLESS"] = "True"

from src import settings


class TestGameSettings(unittest.TestCase):
    def test_dimensions(self) -> None:
        """Verifies game screen dimensions are positive integers."""
        self.assertGreater(settings.SCREEN_WIDTH, 0)
        self.assertGreater(settings.SCREEN_HEIGHT, 0)
        self.assertGreater(settings.FPS, 0)

    def test_title(self) -> None:
        """Verifies title is defined."""
        self.assertTrue(len(settings.TITLE) > 0)

    def test_colors(self) -> None:
        """Verifies RGB color tuples."""
        self.assertEqual(len(settings.COLOR_BACKGROUND), 3)
        self.assertEqual(len(settings.COLOR_PRIMARY), 3)
