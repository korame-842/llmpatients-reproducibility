"""Encoder revision and failure contracts, without weights or networking."""
import sys
import unittest
from types import ModuleType
from unittest.mock import Mock, patch

from agent.core.encoder import ENCODER_MODEL_ID, ENCODER_REVISION, load_encoder


class TestEncoderRevision(unittest.TestCase):
    def setUp(self):
        module = ModuleType("sentence_transformers")
        self.constructor = Mock()
        module.SentenceTransformer = self.constructor
        patcher = patch.dict(sys.modules, {"sentence_transformers": module})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_runtime_loading_binds_revision_and_preserves_device(self):
        result = load_encoder(device="xpu")
        self.constructor.assert_called_once_with(
            ENCODER_MODEL_ID, revision=ENCODER_REVISION,
            device="xpu", local_files_only=False,
        )
        self.assertIs(result, self.constructor.return_value)

    def test_offline_loading_binds_the_same_revision(self):
        load_encoder(device="cpu", local_files_only=True)
        self.constructor.assert_called_once_with(
            ENCODER_MODEL_ID, revision=ENCODER_REVISION,
            device="cpu", local_files_only=True,
        )

    def test_missing_revision_never_falls_back_to_an_alias(self):
        error = OSError("Required synthetic cache revision is unavailable")
        self.constructor.side_effect = error
        with self.assertRaises(OSError) as raised:
            load_encoder(local_files_only=True)
        self.assertIs(raised.exception, error)
        self.constructor.assert_called_once_with(
            ENCODER_MODEL_ID, revision=ENCODER_REVISION,
            device="cpu", local_files_only=True,
        )


if __name__ == "__main__":
    unittest.main()
