import json
import logging
import math
import time
import uuid

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.blockchain.backends import get_adapter
from apps.blockchain.tasks import store_string_in_ipfs
from apps.user.user_profile.models import Profile


class Command(BaseCommand):
    help = "Writes test messages into the blockchain. Can be used for kind of a load testing."

    def add_arguments(self, parser):
        parser.add_argument(
            'amount',
            type=int,
            help='Total number of messages to send.'
        )
        parser.add_argument(
            '--batch_size',
            type=int,
            default=100, # Sensible default batch size
            help='Number of messages to send in each batch before pausing. Default: 100.'
        )
        parser.add_argument(
            '--timeout_seconds',
            type=int,
            default=5, # Default pause duration
            help='Number of seconds to wait between sending batches. Default: 5.'
        )

    # def handle(self, *args, **options):
    #     amount = options['amount'][0]
    #     timeout_after = options['timeout_after'][0]
    #
    #     adapter = get_adapter()()
    #     node = Profile.objects.get(identifier=settings.IDENTIFIER)
    #     priv_key = node.get_private_key()
    #     if priv_key is None:
    #         print("Node has no private key.")
    #         return
    #
    #     tj = amount // timeout_after
    #     for j in range(tj):
    #
    #         msgs = []
    #         for i in range(j):
    #             msg = {"header": {"topics": ["log"]}, "data": [{"validator": "json", "value": {"action": "test",
    #                                                                                      "actor": {"identifier": "umg.centauron.io",
    #                                                                                                "display": "umg.centauron.io",
    #                                                                                                "model": "node",
    #                                                                                                "organization": "did:firefly:org/umgOrg"},
    #                                                                                            "context": None,
    #                                                                                            "object": {"model": "node", "value": {"identifier": "umg.centauron.io", "display": "umg.centauron.io", "model": "node"}}}}]}
    #             d = store_string_in_ipfs(msg)
    #             msgs.append(json.dumps({'type': 'broadcast', 'cid': d['Hash'], 'i': i, 'id': str(uuid.uuid4())}))
    #
    #         adapter.send_multiple_txs(priv_key, msgs)
    #
    #         time.sleep(5)


    def handle(self, *args, **options):
        amount = options['amount']
        batch_size = options['batch_size']
        timeout_seconds = options['timeout_seconds']

        if amount <= 0:
            self.stdout.write(self.style.ERROR("Amount must be greater than 0."))
            return
        if batch_size <= 0:
            self.stdout.write(self.style.ERROR("Batch size must be greater than 0."))
            return
        if timeout_seconds < 0:
            self.stdout.write(self.style.WARNING("Timeout seconds is negative, using 0."))
            timeout_seconds = 0

        self.stdout.write(f"Attempting to send {amount} total messages.")
        self.stdout.write(f"Batch size: {batch_size}, Pause between batches: {timeout_seconds}s")

        try:
            adapter_class = get_adapter()
            adapter = adapter_class() # Instantiate the adapter
            adapter.connect()
            node = Profile.objects.get(identifier=settings.IDENTIFIER)
            priv_key = node.get_private_key()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to initialize adapter or node profile: {e}"))
            return

        if priv_key is None:
            self.stdout.write(self.style.ERROR(f"Node {settings.IDENTIFIER} has no private key configured."))
            return

        num_batches = math.ceil(amount / batch_size)
        self.stdout.write(f"This will require approximately {num_batches} batch(es).")

        messages_sent_count = 0
        for batch_num in range(num_batches):
            start_index = batch_num * batch_size
            # Determine the actual size of this specific batch (handles the last partial batch)
            current_batch_size = min(batch_size, amount - messages_sent_count)

            if current_batch_size <= 0:
                break # Should not happen with ceil logic, but good safeguard

            self.stdout.write(f"\n--- Preparing Batch {batch_num + 1} of {num_batches} (Size: {current_batch_size}) ---")

            msgs_payloads = []
            for i in range(current_batch_size):
                # Overall message index across all batches
                overall_msg_index = start_index + i

                # Create the message structure
                msg_content = {"header": {"topics": ["log"], "i": i}, "data": [{"validator": "json", "value": {"action": "test",
                                                                                                     "actor": {"identifier": "umg.centauron.io",
                                                                                                               "display": "umg.centauron.io",
                                                                                                               "model": "node",
                                                                                                               "organization": "did:firefly:org/umgOrg"},
                                                                                                           "context": None,
                                                                                                           "object": {"model": "node", "value": {"identifier": "umg.centauron.io", "display": "umg.centauron.io", "model": "node"}}}}]}


                try:
                    # Store the content in IPFS (this might be slow if synchronous)
                    ipfs_result = store_string_in_ipfs(json.dumps(msg_content))
                    if not ipfs_result or 'Hash' not in ipfs_result:
                        self.stdout.write(self.style.ERROR(f"Failed to store message {overall_msg_index} content in IPFS. Skipping message."))
                        continue # Skip this message

                    cid = ipfs_result['Hash']
                    # Prepare the final payload for the blockchain transaction
                    tx_payload = {
                        'type': 'broadcast',
                        'cid': cid,
                        'msg_index': overall_msg_index, # Include overall index in tx data
                        'id':str(uuid.uuid4()),
                        'batch': batch_num,
                    }
                    msgs_payloads.append(json.dumps(tx_payload))
                    self.stdout.write(f"  Prepared message {overall_msg_index} (CID: {cid})")

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error preparing message {overall_msg_index}: {e}"))
                    logging.exception(e)
                    # Decide if you want to stop the whole process or just skip the message
                    # break # Uncomment to stop entire command on error

            if not msgs_payloads:
                self.stdout.write(self.style.WARNING(f"Batch {batch_num + 1} prepared no messages (check IPFS errors)."))
                continue # Skip to next batch or finish

            # Send the batch of transaction payloads
            self.stdout.write(f"--- Sending Batch {batch_num + 1} ({len(msgs_payloads)} messages) to blockchain ---")
            try:
                tx_hashes = adapter.send_multiple_txs(priv_key, msgs_payloads)
                messages_sent_count += len(msgs_payloads)
                self.stdout.write(self.style.SUCCESS(f"Batch {batch_num + 1} sent. Tx Hashes: {tx_hashes}"))
                self.stdout.write(f"Total messages sent so far: {messages_sent_count}/{amount}")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error sending Batch {batch_num + 1}: {e}"))
                self.stdout.write(self.style.ERROR("Stopping command due to blockchain sending error."))
                logging.exception(e)
                break # Stop the process if sending fails

            # Pause between batches, but NOT after the very last batch
            if messages_sent_count < amount and timeout_seconds > 0:
                self.stdout.write(f"\nWaiting for {timeout_seconds} seconds before next batch...")
                time.sleep(timeout_seconds)

        self.stdout.write(f"\n--- Command Finished ---")
        self.stdout.write(f"Successfully sent {messages_sent_count} out of {amount} requested messages.")

