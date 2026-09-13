from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from api.errors import EmbeddingProviderUnavailable


class RunEmbeddingsCommandTests(SimpleTestCase):
    @patch("api.ai.embed_annotations")
    def test_successful_embedding_run_returns_normally(self, embed_annotations):
        call_command("run_embs")
        embed_annotations.assert_called_once_with()

    @patch(
        "api.ai.embed_annotations",
        side_effect=EmbeddingProviderUnavailable("temporary DNS failure"),
    )
    def test_provider_outage_does_not_exit_nonzero(self, embed_annotations):
        stderr = StringIO()

        call_command("run_embs", stderr=stderr)

        embed_annotations.assert_called_once_with()
        self.assertIn("Embedding startup task skipped", stderr.getvalue())
        self.assertIn("Pending notes will remain marked for embedding", stderr.getvalue())

    @patch("api.ai.embed_annotations", side_effect=RuntimeError("unexpected failure"))
    def test_unexpected_embedding_error_is_also_isolated(self, _embed_annotations):
        stderr = StringIO()

        call_command("run_embs", stderr=stderr)

        self.assertIn("unexpected failure", stderr.getvalue())
