from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("api", "0043_document_toc_cancellation")]

    operations = [
        migrations.AddField(
            model_name="document",
            name="toc_progress",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="document",
            name="toc_progress_message",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
    ]
