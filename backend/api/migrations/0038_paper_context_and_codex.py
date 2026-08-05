from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0037_document_ocr_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="absolute_local_path",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="document",
            name="context_created_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="context_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="document",
            name="context_status",
            field=models.CharField(db_index=True, default="not_started", max_length=32),
        ),
        migrations.AddField(
            model_name="document",
            name="context_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="document_hash",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="document",
            name="file_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="document",
            name="page_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="chatlogs",
            name="codex_thread_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="chatlogs",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="chatlogs",
            name="document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="chat_logs",
                to="api.document",
            ),
        ),
        migrations.AddField(
            model_name="chatlogs",
            name="provider",
            field=models.CharField(db_index=True, default="legacy", max_length=32),
        ),
        migrations.CreateModel(
            name="DocumentPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("page_number", models.PositiveIntegerField()),
                ("extracted_text", models.TextField(blank=True, default="")),
                ("text_blocks", models.JSONField(blank=True, default=list)),
                ("page_image_path", models.TextField(blank=True, default="")),
                ("thumbnail_path", models.TextField(blank=True, default="")),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("embedded", "Embedded text"),
                            ("ocr", "OCR"),
                            ("combined", "Embedded text and OCR"),
                            ("failed", "Extraction failed"),
                        ],
                        default="embedded",
                        max_length=16,
                    ),
                ),
                ("ocr_used", models.BooleanField(default=False)),
                ("ocr_confidence", models.FloatField(blank=True, null=True)),
                ("width", models.FloatField(default=0)),
                ("height", models.FloatField(default=0)),
                ("rotation", models.SmallIntegerField(default=0)),
                ("visually_complex", models.BooleanField(db_index=True, default=False)),
                ("complexity_reasons", models.JSONField(blank=True, default=list)),
                ("extraction_error", models.TextField(blank=True, default="")),
                ("ocr_cache_key", models.CharField(blank=True, default="", max_length=128)),
                ("renderer_version", models.CharField(blank=True, default="", max_length=64)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="context_pages",
                        to="api.document",
                    ),
                ),
            ],
            options={"ordering": ["page_number"]},
        ),
        migrations.CreateModel(
            name="DocumentChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_id", models.CharField(max_length=96, unique=True)),
                ("start_page", models.PositiveIntegerField()),
                ("end_page", models.PositiveIntegerField()),
                ("chunk_text", models.TextField()),
                ("normalized_text", models.TextField(blank=True, default="")),
                ("section_title", models.CharField(blank=True, default="", max_length=512)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="context_chunks",
                        to="api.document",
                    ),
                ),
            ],
            options={"ordering": ["start_page", "id"]},
        ),
        migrations.AddConstraint(
            model_name="documentpage",
            constraint=models.UniqueConstraint(
                fields=("document", "page_number"),
                name="unique_context_page_per_document",
            ),
        ),
        migrations.AddIndex(
            model_name="documentchunk",
            index=models.Index(fields=["document", "start_page"], name="api_documen_documen_76bf5b_idx"),
        ),
    ]
