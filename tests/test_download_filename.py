import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.export import generate_clean_download_filename


class TestDownloadFilename(unittest.TestCase):
    def test_prompt_examples(self):
        """Test the exact examples specified in the user requirements."""
        self.assertEqual(
            generate_clean_download_filename("processed_Module_24_20261112_081146_f87e54.mp4"),
            "processed_Module_24.mp4",
        )
        self.assertEqual(
            generate_clean_download_filename("processed_My_Video_20261112_081146_f87e54.mp4"),
            "processed_My_Video.mp4",
        )

    def test_various_extensions(self):
        """Preserve original video extensions."""
        self.assertEqual(
            generate_clean_download_filename("processed_Module_24_20261112_081146_f87e54.mov"),
            "processed_Module_24.mov",
        )
        self.assertEqual(
            generate_clean_download_filename("processed_Module_24_20261112_081146_f87e54.mkv"),
            "processed_Module_24.mkv",
        )
        self.assertEqual(
            generate_clean_download_filename("processed_Module_24_20261112_081146_f87e54.webm"),
            "processed_Module_24.webm",
        )

    def test_broll_prefix(self):
        """B-roll output names should retain broll_ prefix and clean timestamp/UUID."""
        self.assertEqual(
            generate_clean_download_filename("broll_Module_24_20261112_081146_f87e54.mp4"),
            "broll_Module_24.mp4",
        )
        self.assertEqual(
            generate_clean_download_filename("broll_sample.mp4"),
            "broll_sample.mp4",
        )

    def test_legacy_exported_prefix(self):
        """Strip redundant exported_ prefix if present."""
        self.assertEqual(
            generate_clean_download_filename("exported_processed_Module_24_20261112_081146_f87e54.mp4"),
            "processed_Module_24.mp4",
        )

    def test_already_clean_names(self):
        """Clean filenames should remain unchanged."""
        self.assertEqual(
            generate_clean_download_filename("processed_Module_24.mp4"),
            "processed_Module_24.mp4",
        )
        self.assertEqual(
            generate_clean_download_filename("processed_My_Video.mp4"),
            "processed_My_Video.mp4",
        )

    def test_timestamp_without_uuid(self):
        """Filename with date/timestamp but no hex uuid suffix."""
        self.assertEqual(
            generate_clean_download_filename("processed_Module_24_20261112_081146.mp4"),
            "processed_Module_24.mp4",
        )

    def test_internal_numbers_preserved(self):
        """Numbers inside the video title should NOT be stripped, only trailing timestamp/uuid."""
        self.assertEqual(
            generate_clean_download_filename("processed_Lesson_2024_Module_12_20261112_081146_f87e54.mp4"),
            "processed_Lesson_2024_Module_12.mp4",
        )

    def test_path_object_input(self):
        """Support Path objects as well as strings."""
        p = Path("/tmp/jobs/job_123/processed_Module_24_20261112_081146_f87e54.mp4")
        self.assertEqual(
            generate_clean_download_filename(p),
            "processed_Module_24.mp4",
        )


if __name__ == "__main__":
    unittest.main()
