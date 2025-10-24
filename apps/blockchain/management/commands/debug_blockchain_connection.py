import httpx
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.blockchain.backends import get_adapter


class Command(BaseCommand):
    help = "Debugs the blockchain connection."

    def handle(self, *args, **options):

        print(f"URL besu: {settings.BLOCKCHAIN_RPC_URL}")
        print(f"URL ipfs: {settings.IPFS_URL}")


        get_adapter()().connect()

        url = f'{settings.IPFS_URL}api/v0/id'
        r = httpx.post(url)
        d = r.json()
        print(d)
