import base64
import json
import logging
import secrets
from typing import Any

from apps.federation.messages import UserMessage, CertificateMessage


class TokenInvalid(Exception):
    """
    Is thrown if a token to be parsed is invalid.
    """

    def __init__(self, *args):
        super().__init__(*args)


def create_token(type: str, description: str, data: dict[str, Any] | str):
    text = f"-- CENTAURON {type}\n"
    text += f"-- {description}\n"
    if isinstance(data, str):
        content = data
    else:
        content = json.dumps(data)
    text += base64.b64encode(content.encode("utf-8")).decode("ascii")
    return text


def parse_token(token):
    lines = token.strip().split("\n")
    if len(lines) != 3:
        logging.error("Token has more or less than exactly 3 lines!")
        raise TokenInvalid("Token is corrupted.")
    if not lines[0].startswith("-- ") or not lines[1].startswith("-- "):
        logging.error("Token starts with wrong line.")
        raise TokenInvalid("Token is corrupted.")

    try:
        dict = json.loads(base64.b64decode(lines[2]))
        type = dict['type']
        if type == 'user':
            return UserMessage(**dict)
        if type == 'certificate':
            return CertificateMessage(**dict)
        # TODO expand list on demand
        return dict
    except Exception as e:
        logging.exception(e)
        raise TokenInvalid(e)


def generate_token() -> str:
    return secrets.token_urlsafe(64)  # 64 byte long random token
