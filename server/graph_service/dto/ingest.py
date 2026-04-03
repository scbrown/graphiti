from datetime import datetime

from pydantic import BaseModel, Field

from graph_service.dto.common import Message


class AddMessagesRequest(BaseModel):
    group_id: str = Field(..., description='The group id of the messages to add')
    messages: list[Message] = Field(..., description='The messages to add')


class AddEntityNodeRequest(BaseModel):
    uuid: str = Field(..., description='The uuid of the node to add')
    group_id: str = Field(..., description='The group id of the node to add')
    name: str = Field(..., description='The name of the node to add')
    summary: str = Field(default='', description='The summary of the node to add')


class ExtractedNode(BaseModel):
    name: str = Field(..., description='Entity name')
    summary: str = Field(default='', description='Entity summary')
    labels: list[str] = Field(default_factory=list, description='Entity labels')


class ExtractedEdge(BaseModel):
    name: str = Field(..., description='Relation name')
    fact: str = Field(..., description='Fact describing the relationship')
    source_node_name: str = Field(..., description='Name of the source node')
    target_node_name: str = Field(..., description='Name of the target node')


class CompleteEpisodeRequest(BaseModel):
    name: str = Field(..., description='Episode name')
    episode_body: str = Field(..., description='Episode content')
    source_description: str = Field(default='', description='Source description')
    reference_time: datetime = Field(..., description='When the event occurred')
    group_id: str = Field(..., description='Graph partition id')
    nodes: list[ExtractedNode] = Field(default_factory=list, description='Pre-extracted nodes')
    edges: list[ExtractedEdge] = Field(default_factory=list, description='Pre-extracted edges')
