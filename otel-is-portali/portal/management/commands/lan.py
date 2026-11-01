"""
Run the development server so phones on the same Wi-Fi can open the site.

    python manage.py lan            # port 8000
    python manage.py lan 9000       # another port
"""
import socket

from django.core.management import call_command
from django.core.management.base import BaseCommand


def local_ip():
    """IP address of this computer in the local network (no data is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Command(BaseCommand):
    help = "Start the dev server on all network interfaces and print the address for your phone."

    def add_arguments(self, parser):
        parser.add_argument("port", nargs="?", default="8000")

    def handle(self, *args, port, **options):
        ip = local_ip()
        line = "=" * 56
        self.stdout.write(self.style.SUCCESS(
            f"\n{line}\n  On this computer:  http://127.0.0.1:{port}\n"
            f"  On your phone:     http://{ip}:{port}\n"
            f"  (phone and computer must be on the same Wi-Fi)\n{line}\n"))
        call_command("runserver", f"0.0.0.0:{port}")
