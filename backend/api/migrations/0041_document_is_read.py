from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0040_rename_api_smartco_status_375e38_idx_api_smartco_status_9c9a34_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="is_read",
            field=models.BooleanField(default=False),
        ),
    ]
