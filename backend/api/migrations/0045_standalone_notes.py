from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("api", "0044_document_toc_progress")]

    operations = [
        migrations.CreateModel(
            name="StandaloneNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(default="Untitled note", max_length=255)),
                ("content", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("embedding_binary", models.BinaryField(blank=True, null=True)),
                ("needs_embedding", models.BooleanField(default=True)),
                ("embedding_provider", models.CharField(blank=True, default="", max_length=32)),
                ("embedding_model", models.CharField(blank=True, default="", max_length=128)),
                ("embedding_dimensions", models.PositiveIntegerField(default=0)),
                ("embedding_version", models.PositiveSmallIntegerField(default=0)),
                ("content_hash", models.CharField(blank=True, default="", max_length=64)),
            ],
        ),
        migrations.AddField(
            model_name="chatlogs",
            name="note",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="chat_logs", to="api.standalonenote"),
        ),
    ]
