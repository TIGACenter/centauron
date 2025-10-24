import json
import logging

import httpx
from django.conf import settings
from eth_account import Account
from kubernetes import config, client
from kubernetes.stream import stream
from web3.auto import w3


def create_keystore(password):
    account = Account.create()
    keystore = Account.encrypt(w3.to_hex(account.key), password, kdf='pbkdf2')
    return keystore


def add_identity_to_ff_signer(password, keystore):
    address = keystore.get('address').lower()
    keystore['address'] = f'0x{address}'
    password = password.replace('"', '\\"')  # escape quote sign just in case it exists in password
    keystore_json = json.dumps(keystore).replace('"', '\\"')
    commands = [
        f'echo "{keystore_json}" > /data/keystore/{address}',
        f'echo "{password}" > /data/passwords/{address}',
        f'cat <<EOF > /data/keystore/{address}.toml\n[metadata]\ncreatedAt = 2019-11-05T08:15:30-05:00\ndescription = "File based configuration"\n\n[signing]\ntype = "file-based-signer"\nkey-file = "/data/keystore/{address}"\npassword-file = "/data/passwords/{address}"\nEOF'
    ]

    commands = ' && '.join(commands)

    config.load_kube_config(config_file=settings.FIREFLY_KIND_CONFIG_FILE, context=settings.FIREFLY_K8S_CONTEXT)
    v1 = client.CoreV1Api()

    pod_name = settings.FIREFLY_SIGNER_POD_NAME
    namespace = settings.FIREFLY_K8S_NAMESPACE

    # Define the command to run
    commands = [
        'sh', '-c', commands
    ]

    # Function to execute a command in the pod
    def exec_command_in_pod(pod_name, namespace, commands):
        # Use the stream function to handle the exec request
        exec_command = stream(
            v1.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=commands,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False
        )
        return exec_command

    output = exec_command_in_pod(pod_name, namespace, commands)


def create_identity(userid, username, wallet_key) -> str:
    # get the id of the parent organization
    url = f'{settings.FIREFLY_API_URL}identities'
    res = httpx.get(url).json()
    parent = [p for p in res if p['did'] == settings.ORGANIZATION_DID][0]
    parent_id = parent['id']

    # create and announce the new identity to the network
    # the did is calculated by firefly with the name as the unique part.
    payload = {
        "type": "custom",
        "parent": parent_id,
        "namespace": settings.FIREFLY_NAMESPACE,
        "name": parent['name'] + '-' + username,
        "key": wallet_key
    }
    res = httpx.post(url, json=payload)
    logging.info(res.status_code)
    logging.info(res.json())
    assert res.status_code == httpx.codes.ACCEPTED
    return res.json()['did']
