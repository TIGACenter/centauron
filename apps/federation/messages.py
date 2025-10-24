import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MessageObject(BaseModel):
    type: str = Field(None)
    content: Any = Field(None)
    '''
    User identifier.
    '''
    sender: str = Field(None)
    '''
    User identifier. If the recipient is null, the message is a broadcast.
    '''
    recipient: str | None = Field(None)


class UserMessageContent(BaseModel):
    identifier: str
    common_name: str
    node_name: str
    address: str
    certificate_thumbprint: Optional[str] = None
    cdn_address: str
    did: str
    api_address: str


class ProfileMessageContent(BaseModel):
    data: Dict[str, str | None] | None
    human_readable: str
    organization: str | None
    identifier: str
    identity: str
    eth_address: str | None


class UserMessage(MessageObject):
    type: str = 'node'
    content: UserMessageContent


#
class ProfileMessage(MessageObject):
    type: str = 'profile'
    content: ProfileMessageContent


class LeaderboardObject(MessageObject):
    type: str = 'leaderboard'
    content: Dict[str, Any]


class ShareObject(MessageObject):
    type: str = 'share'


class SubmissionObject(MessageObject):
    type: str = 'submission'


class SubmissionResultObject(MessageObject):
    type: str = 'submission-result'


class RetractShareMessageContent(BaseModel):
    identifier: str


class RetractShareMessage(MessageObject):
    type: str = 'retract-share'
    content: RetractShareMessageContent


class CertificateMessageContent(BaseModel):
    certificate: str
    recipient: str
    issuer: str
    valid_until: datetime.datetime


class CertificateMessage(MessageObject):
    type: str = 'certificate'
    content: CertificateMessageContent


class ProjectMessageContent(BaseModel):
    type: str = 'project'
    id: str
    identifier: str
    name: str
    description: str | None = Field(default=None)
    origin: str | None


class GroundTruthSchemaContent(BaseModel):
    type: str = 'ground-truth-schema'
    identifier: str
    name: str
    yaml: str
    project: str


class TestMessageContent(BaseModel):
    type: str = 'test'
    model: str
    value: str | Dict[str, Any]


class ProjectInviteResponseContent(BaseModel):
    '''
    the identifier of the project the user was invited for.
    '''
    project: str
    accept: bool


class GroundTruthSchemaMessageObject(MessageObject):
    type: str = 'ground-truth-schema'
    content: GroundTruthSchemaContent


class DataViewMessageContent(BaseModel):
    type: str = 'data-view'
    name: str
    query: Dict[str, Any]
    datatable_config: str
    model: str


class ProjectInviteAcceptMessage(BaseModel):
    accept: bool
    project: str


class ProjectInviteObject(MessageObject):
    type: str = 'project-invitation'
    content: List[ProjectMessageContent | DataViewMessageContent | GroundTruthSchemaContent]


class ProjectInviteResponseObject(MessageObject):
    type: str = 'project-invitation-response'
    content: ProjectInviteResponseContent


class ProjectObject(MessageObject):
    type: str = 'project'
    content: List[ProjectMessageContent | DataViewMessageContent | GroundTruthSchemaContent]


class GroundTruthSchemaObject(MessageObject):
    type: str = 'ground-truth-schema'
    content: GroundTruthSchemaContent


class ProjectInvitationObject(MessageObject):
    type: str = 'project-invitation-response'
    content: ProjectInviteAcceptMessage


class AckObject(MessageObject):
    type: str = 'ack'


class TestObject(MessageObject):
    type: str = 'test'
    content: TestMessageContent


class Message(BaseModel):
    class Config:
        populate_by_name = True

    type: str = Field(None)
    object: MessageObject|Dict[str,Any] = Field(None)
    from_: str = Field(alias='from')
    to: str | None


# @dataclass
class CreateMessage(Message):
    type: str = 'create'


class DeleteMessage(Message):
    type: str = 'delete'


# @dataclass
class UpdateMessage(Message):
    type: str = 'update'


class TestMessage(Message):
    type: str = 'test'


# @dataclass(kw_only=True)
class AckMessage(Message):
    type: str = 'ack'
