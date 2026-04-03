import asyncio
from contextlib import asynccontextmanager
from functools import partial

from fastapi import APIRouter, FastAPI, HTTPException, status
from graphiti_core.edges import EntityEdge  # type: ignore
from graphiti_core.nodes import EntityNode, EpisodeType  # type: ignore
from graphiti_core.utils.maintenance.graph_data_operations import clear_data  # type: ignore

from graph_service.dto import (
    AddEntityNodeRequest,
    AddMessagesRequest,
    CompleteEpisodeRequest,
    Message,
    Result,
)
from graph_service.zep_graphiti import ZepGraphitiDep


class AsyncWorker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.task = None

    async def worker(self):
        while True:
            try:
                print(f'Got a job: (size of remaining queue: {self.queue.qsize()})')
                job = await self.queue.get()
                await job()
            except asyncio.CancelledError:
                break

    async def start(self):
        self.task = asyncio.create_task(self.worker())

    async def stop(self):
        if self.task:
            self.task.cancel()
            await self.task
        while not self.queue.empty():
            self.queue.get_nowait()


async_worker = AsyncWorker()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await async_worker.start()
    yield
    await async_worker.stop()


router = APIRouter(lifespan=lifespan)


@router.post('/messages', status_code=status.HTTP_202_ACCEPTED)
async def add_messages(
    request: AddMessagesRequest,
    graphiti: ZepGraphitiDep,
):
    async def add_messages_task(m: Message):
        await graphiti.add_episode(
            uuid=m.uuid,
            group_id=request.group_id,
            name=m.name,
            episode_body=f'{m.role or ""}({m.role_type}): {m.content}',
            reference_time=m.timestamp,
            source=EpisodeType.message,
            source_description=m.source_description,
        )

    for m in request.messages:
        await async_worker.queue.put(partial(add_messages_task, m))

    return Result(message='Messages added to processing queue', success=True)


@router.post('/entity-node', status_code=status.HTTP_201_CREATED)
async def add_entity_node(
    request: AddEntityNodeRequest,
    graphiti: ZepGraphitiDep,
):
    node = await graphiti.save_entity_node(
        uuid=request.uuid,
        group_id=request.group_id,
        name=request.name,
        summary=request.summary,
    )
    return node


@router.delete('/entity-edge/{uuid}', status_code=status.HTTP_200_OK)
async def delete_entity_edge(uuid: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_entity_edge(uuid)
    return Result(message='Entity Edge deleted', success=True)


@router.delete('/group/{group_id}', status_code=status.HTTP_200_OK)
async def delete_group(group_id: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_group(group_id)
    return Result(message='Group deleted', success=True)


@router.delete('/episode/{uuid}', status_code=status.HTTP_200_OK)
async def delete_episode(uuid: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_episodic_node(uuid)
    return Result(message='Episode deleted', success=True)


@router.post('/clear', status_code=status.HTTP_200_OK)
async def clear(
    graphiti: ZepGraphitiDep,
):
    await clear_data(graphiti.driver)
    await graphiti.build_indices_and_constraints()
    return Result(message='Graph cleared', success=True)


@router.post('/episodes/complete', status_code=status.HTTP_201_CREATED)
async def complete_episode(
    request: CompleteEpisodeRequest,
    graphiti: ZepGraphitiDep,
):
    """Ingest an episode with pre-extracted nodes and edges.

    Crew agents perform extraction — this endpoint writes the results
    to FalkorDB via ingest_extracted_episode(). No LLM calls.
    """
    # Build EntityNode objects from the simplified request format
    nodes: list[EntityNode] = []
    node_name_to_uuid: dict[str, str] = {}
    for n in request.nodes:
        entity = EntityNode(
            name=n.name,
            group_id=request.group_id,
            summary=n.summary,
            labels=n.labels,
        )
        nodes.append(entity)
        node_name_to_uuid[n.name] = entity.uuid

    # Build EntityEdge objects, resolving source/target names to UUIDs
    edges: list[EntityEdge] = []
    for e in request.edges:
        source_uuid = node_name_to_uuid.get(e.source_node_name)
        target_uuid = node_name_to_uuid.get(e.target_node_name)
        if source_uuid is None or target_uuid is None:
            missing = []
            if source_uuid is None:
                missing.append(f'source_node_name={e.source_node_name!r}')
            if target_uuid is None:
                missing.append(f'target_node_name={e.target_node_name!r}')
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f'Edge {e.name!r} references unknown node(s): {", ".join(missing)}. '
                f'All edge endpoints must be defined in the nodes list.',
            )
        edge = EntityEdge(
            name=e.name,
            fact=e.fact,
            group_id=request.group_id,
            source_node_uuid=source_uuid,
            target_node_uuid=target_uuid,
            created_at=request.reference_time,
        )
        edges.append(edge)

    results = await graphiti.ingest_extracted_episode(
        name=request.name,
        episode_body=request.episode_body,
        source_description=request.source_description,
        reference_time=request.reference_time,
        nodes=nodes,
        edges=edges,
        group_id=request.group_id,
    )

    return {
        'episode_uuid': results.episode.uuid,
        'nodes': [{'uuid': n.uuid, 'name': n.name} for n in results.nodes],
        'edges': [
            {
                'uuid': e.uuid,
                'name': e.name,
                'source_node_uuid': e.source_node_uuid,
                'target_node_uuid': e.target_node_uuid,
            }
            for e in results.edges
        ],
    }
