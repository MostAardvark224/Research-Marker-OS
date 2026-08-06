from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the Research Marker MCP stdio server for Claude Desktop / Cowork"

    def handle(self, *args, **options):
        from api.mcp.server import main

        main()
