from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Runs the batch embedding process for pending annotations'

    def handle(self, *args, **kwargs):
        # Embeddings are an optional startup task. A missing credential,
        # exhausted quota, or temporary network outage must not exit this
        # process and cause the Procfile supervisor to terminate the web app.
        try:
            from api.ai import embed_annotations

            embed_annotations()
        except Exception as exc:
            self.stderr.write(
                self.style.WARNING(
                    f"Embedding startup task skipped: {exc}. "
                    "Pending notes will remain marked for embedding."
                )
            )
