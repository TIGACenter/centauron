from eth_account import Account
from hexbytes import HexBytes
from web3.auto import w3
import json

password = "P6v7mr2d70"

def create_keystore(password):
    account = Account.create()
    keystore = Account.encrypt(w3.to_hex(account.key), password, kdf='pbkdf2')
    return keystore

keystore = create_keystore(password)
address = keystore.get('address').lower()
keystore['address'] = f'0x{address}'
password = password.replace('"', '\\"')  # escape quote sign just in case it exists in password
keystore_json = json.loads(json.dumps(keystore))


print(keystore_json)
print(keystore)
print(len("a33f4da266a653ea10d42fd7be1a20"))
print(len(keystore_json['crypto']['cipherparams']['iv']))


j = {"address": "0x432ba7673fc9ff5f47dca4e548075edaf6abe90f", "crypto": {"cipher": "aes-128-ctr", "cipherparams": {"iv": "a33f4da266a653ea10d42fd7be1a20"}, "ciphertext": "435572c376286d28c1e57daea7a33d157bb0190aae023fcbf469e8e03e7a247d", "kdf": "pbkdf2", "kdfparams": {"c": 1000000, "dklen": 32, "prf": "hmac-sha256", "salt": "25dd1f920135a0d687f1095b77d7c7f5"}, "mac": "a539793cab6ec7d19c591762dc37ebc236cde27fb268098dbef4ca73ab1746c8"}, "id": "63e46a81-9a97-4c9a-a39e-03e72502a8ed", "version": 3}
j = {"address": "0x432ba7673fc9ff5f47dca4e548075edaf6abe90f", "crypto": {"cipher": "aes-128-ctr", "cipherparams": {"iv": "a33f4da266a653ea10d42fd7be1a20"}, "ciphertext": "435572c376286d28c1e57daea7a33d157bb0190aae023fcbf469e8e03e7a247d", "kdf": "pbkdf2", "kdfparams": {"c": 1000000, "dklen": 32, "prf": "hmac-sha256", "salt": "25dd1f920135a0d687f1095b77d7c7f5"}, "mac": "a539793cab6ec7d19c591762dc37ebc236cde27fb268098dbef4ca73ab1746c8"}, "id": "63e46a81-9a97-4c9a-a39e-03e72502a8ed", "version": 3}
k = Account.decrypt(j, "nQHE0jac0Y")
a = Account.from_key(k)

print(a, a.address)
