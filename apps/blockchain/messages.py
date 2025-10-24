from typing import Literal, Dict, Any

from pydantic import BaseModel


class Identifiable(BaseModel):
    identifier: str
    display: str | None
    model: Literal["node", "project", "dataset", "challenge", "user", "submission"] | None


class Actor(Identifiable):
    organization: str | None


class Object(BaseModel):
    model: Literal["node", "project", "dataset", "challenge", "user", "slide", "file", "submission"] | None
    value: list[str | Dict | Identifiable | int] | Dict[str, Any] | Identifiable


class Message(BaseModel):
    action: Literal["share", "add", "create", "use"]
    actor: Actor
    context: Dict[str, Identifiable] | None = None
    object: Object


class ShareMessage(Message):
    action: str = 'share'


class AddMessage(Message):
    action: str = 'add'


class CreateMessage(Message):
    action: str = 'create'


class UseMessage(Message):
    action: str = "use"


class ExportMessage(Message):
    action: str = "export"

class DownloadMessage(Message):
    action:str = 'download'

class UnknownMessage(Message):
    action: str = "unknown"

class SubmissionSentMessage(Message):
    action: str = 'submission-sent'

class TestMessage(Message):
    action: str = 'test'
