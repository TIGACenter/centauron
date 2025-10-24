import json
import logging
import threading
import time
from importlib import import_module

import httpx
from django.conf import settings
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from apps.blockchain.client import on_message
from apps.blockchain.models import LastSeenBlock, Block

# provide a sane default?
BLOCKCHAIN_BACKEND = getattr(settings, 'BLOCKCHAIN_BACKEND', 'apps.blockchain.backends.PollingAdapter')

def get_adapter():
    # grab the classname off of the backend string
    package, klass = BLOCKCHAIN_BACKEND.rsplit('.', 1)

    # dynamically import the module, in this case app.backends.adapter_a
    module = import_module(package)

    # pull the class off the module and return
    return getattr(module, klass)


class BlockchainBaseAdapter:

    def start(self):
        pass

class PollingAdapter(BlockchainBaseAdapter):

    def __init__(self):
        self.nonce_lock = threading.Lock()
        self.w3 = None

    def get_polling_frequency(self):
        '''
        Returns the polling frequency in seconds.
        '''
        return settings.BLOCKCHAIN_POLLING_FREQUENCY or 5

    def connect(self):
        url = settings.BLOCKCHAIN_RPC_URL
        w3 = Web3(Web3.HTTPProvider(url))
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        if not w3.is_connected():
            logging.error(f"Failed to connect to the node at {url}. Please check the RPC URL.")
            return None
        logging.info(f"Connected to {url} successfully.")
        self.w3 = w3
        return w3

    def _prepare_and_send_tx(self, private_key: str, payload: str, nonce: int):
        """
        Internal method to prepare, sign, and send a single transaction
        with a PRE-DETERMINED nonce and ZERO GAS PRICE.
        """
        # if not self._ensure_connected():
        #     raise ConnectionError("Cannot send transaction: Not connected to blockchain node.")

        # w3 = self.w3
        sender_account = self.w3.eth.account.from_key(private_key)
        sender_address = sender_account.address
        recipient_address = sender_address
        hex_data = "0x" + payload.encode('utf-8').hex()
        chain_id = self.w3.eth.chain_id

        tx_dict_base = {
            'to': recipient_address,
            'value': 0,
            'gas': 0, # Estimate below
            'gasPrice': 0, # <-- HARDCODED TO ZERO for private zero-fee network
            'nonce': nonce,
            'data': hex_data,
            'chainId': chain_id,
        }
        logging.debug("Using hardcoded gasPrice: 0")

        try:
            # Estimate gas limit - still useful to prevent out-of-gas errors
            estimated_gas = self.w3.eth.estimate_gas(tx_dict_base)
            tx_dict_base['gas'] = int(estimated_gas * 1.5) # 50% buffer
            logging.debug(f"Using Gas Limit: {tx_dict_base['gas']} (Estimated: {estimated_gas})")
        except Exception as e:
            # Gas estimation might fail on some private networks or if tx is invalid
            # Provide a generous default gas limit. Adjust if needed.
            default_gas_limit = 200000
            logging.warning(f"Gas estimation failed: {e}. Using default gas limit: {default_gas_limit}")
            tx_dict_base['gas'] = default_gas_limit

        logging.info(f"Preparing Tx: Nonce={nonce}, Payload='{payload[:30]}...', GasLimit={tx_dict_base['gas']}")

        signed_tx = self.w3.eth.account.sign_transaction(tx_dict_base, sender_account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logging.info(f"Sent Tx (Nonce: {nonce}, Hash: {tx_hash.hex()})")
        return tx_hash

    def send_multiple_txs(self, private_key: str, payloads: list[str]):

        sender_address = self.w3.eth.account.from_key(private_key).address
        sent_tx_hashes = []

        with self.nonce_lock:
            try:
                initial_nonce = self.w3.eth.get_transaction_count(sender_address, 'pending')
                logging.info(f"Starting batch send from {sender_address}. Initial pending nonce: {initial_nonce}")

                for i, payload in enumerate(payloads):
                    current_nonce = initial_nonce + i
                    try:
                        tx_hash = self._prepare_and_send_tx(
                            private_key=private_key,
                            payload=payload,
                            nonce=current_nonce
                        )
                        sent_tx_hashes.append(tx_hash.hex())
                        # time.sleep(0.05) # Optional small sleep

                    except Exception as e:
                        logging.exception(f"Error sending transaction for payload '{payload}' with nonce {current_nonce}: {e}")
                        logging.error("Stopping batch send due to error. Subsequent payloads NOT sent.")
                        break
            except Exception as e:
                logging.exception(f"Failed to initiate batch send for {sender_address}: {e}")

        return sent_tx_hashes

    def write_tx(self, w3, private_key, payload:str):
        if w3 is None:
            w3 = self.connect()
        logging.debug(f"Writing {payload} into tx.")
        sender_account = w3.eth.account.from_key(private_key)
        sender_address = sender_account.address
        recipient_address = sender_address
        hex_data = "0x" + payload.encode('utf-8').hex()
        nonce = w3.eth.get_transaction_count(sender_address)
        chain_id = w3.eth.chain_id
        gas_price = 0
        tx_dict = {
            'to': recipient_address,
            'value': 0,
            'gas': 0, # Estimate below
            'gasPrice': gas_price,
            'nonce': nonce,
            'data': hex_data,
            'chainId': chain_id,
        }

        try:
            # Estimate gas - Provide a buffer
            estimated_gas = w3.eth.estimate_gas(tx_dict)
            tx_dict['gas'] = int(estimated_gas * 1.2)
            print(f"Using Gas Limit: {tx_dict['gas']} (Estimated: {estimated_gas})")
        except Exception as e:
            print(f"Gas estimation failed: {e}. Using default limit.")
            # Provide a sensible default, might need adjustment
            tx_dict['gas'] = 100000 # Generous for simple data tx
            print(f"Using default Gas Limit: {tx_dict['gas']}")
        signed_tx = w3.eth.account.sign_transaction(tx_dict, sender_account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        return tx_hash


    def start(self):

        self.download_cid_for_blocks_without_message()

        frequency = self.get_polling_frequency()
        last_block = LastSeenBlock.objects.first()
        if not last_block:
            LastSeenBlock.objects.create(block="0")
            last_processed_block = 0
        else:
            last_processed_block = int(last_block.block)

        w3 = self.connect()
        if not w3:
            return
        logging.info(f"Starting at block: {last_processed_block}")
        while True:

            latest_block = w3.eth.block_number
            # Process blocks one by one from last processed up to current latest
            while last_processed_block < latest_block:
                current_block_num_to_process = last_processed_block + 1
                logging.info(f"-- Processing Block: {current_block_num_to_process} --")
                try:
                    # Fetch block with full transaction objects
                    block = w3.eth.get_block(current_block_num_to_process, full_transactions=True)
                    if block and block.transactions:
                        logging.info(f"   Found {len(block.transactions)} transactions.")
                        for tx in block.transactions:
                            # Check input data for the desired pattern
                            ret = self.decode_and_check_tx_data(tx['input'])
                            if ret is None:
                                logging.warning("CID not included in received block.")
                                continue
                            parsed_data, cid = ret
                            if parsed_data is not None and cid is not None:
                                logging.info(f"Broadcast found in tx {tx.hash.hex()})")
                                self.process(cid, parsed_data, block.number, tx)
                    elif block:
                        logging.debug("   Block contains no transactions.")
                    else:
                        logging.error("get_block returned None.")

                    last_processed_block = current_block_num_to_process # Mark block as processed

                except Exception as e:
                    logging.exception(e)
                    last_processed_block = current_block_num_to_process # Move past potentially problematic block


            LastSeenBlock.objects.update(block=str(last_processed_block))
            logging.debug(f"Updating last seen block to: {last_processed_block}")
            time.sleep(frequency)


    def decode_and_check_tx_data(self, input_data_hex):
        """
        Attempts to decode hex input data as UTF-8 JSON and check for specific attributes.
        Returns the 'cid' value if conditions are met, otherwise None.
        """
        if not input_data_hex or input_data_hex == '0x':
            return None # No input data
        # print(input_data_hex)
        # try:
        #     # 1. Decode Hex to Bytes
        #     input_data_bytes = bytes.fromhex(input_data_hex[2:]) # Remove '0x' prefix
        # except ValueError:
        #     print(f"Debug: Data not valid hex: {input_data_hex[:50]}...") # Uncomment for debugging
        #     return None # Not valid hex

        try:
            # 2. Decode Bytes to String (assuming UTF-8)
            input_data_str = input_data_hex.decode('utf-8')
        except UnicodeDecodeError:
            logging.error(f"Debug: Data not valid UTF-8: {input_data_hex[:50]}...") # Uncomment for debugging
            return None # Not valid UTF-8

        try:
            # 3. Parse String as JSON
            parsed_data = json.loads(input_data_str)
        except json.JSONDecodeError:
            logging.error(f"Debug: Data not valid JSON: {input_data_str[:50]}...") # Uncomment for debugging
            return None # Not valid JSON

        # 4. Check JSON structure and specific attributes
        if isinstance(parsed_data, dict) and \
            parsed_data.get("type") == "broadcast" and \
            "cid" in parsed_data:
            cid_value = parsed_data['cid']
            return parsed_data, str(cid_value) # Return CID as string
        else:
            # Doesn't match criteria (not a dict, type!=broadcast, or missing cid)
            return None

    def process(self, cid, tx_input, block_number, tx):
        """
        :param data: dict with the data
        :param tx: the hash of the tx that contained the broadcast.
        :return:
        """
        message_hash = '0x'+tx['hash'].hex()
        qs = Block.objects.filter(
            message_hash=message_hash,
        )
        if not qs.exists():
            block = Block.objects.create(
                number=block_number,
                tx=json.loads(Web3.to_json(tx)),
                cid=cid,
                tx_content=tx_input,
                message_hash=message_hash,
            )
            self.download_message_and_save(block)

    def download_message_and_save(self, block):
        try:
            msg = self.download_from_ipfs(block.cid)
            content = self.prepare_message(msg)
            block.content = content
            block.cid_downloaded = True
            block.save()
            on_message(None, block)
        except Exception as e:
            logging.exception(e)


    def prepare_message(self, content):
        if not isinstance(content, str):
            content = json.dumps(content)
        return content

    def download_from_ipfs(self, cid):
        logging.info(f'Downloading message from ipfs with CID {cid}')
        url = f'{settings.IPFS_URL}api/v0/cat?arg={cid}'
        logging.info(url)
        response = httpx.post(url, timeout=settings.IPFS_TIMEOUT)
        if response.status_code != 200:
            logging.error(response.content)
        response.raise_for_status()
        try:
            return response.json()
        except Exception as e:
            logging.exception(e)
            return None


    def download_cid_for_blocks_without_message(self):
        qs = Block.objects.filter(cid_downloaded=False)
        logging.info(f"Restoring {qs.count()} blocks that have no messages downloaded yet.")

        for block in qs:
            self.download_message_and_save(block)

        logging.info(f"Restoring blocks done.")
