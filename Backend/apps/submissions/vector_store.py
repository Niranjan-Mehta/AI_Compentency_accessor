"""Local persistent Chroma storage with mandatory submission scoping."""

import atexit
import hashlib
from threading import RLock

import chromadb
from chromadb.config import Settings as ChromaSettings
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .embedding_providers import get_embedding_provider


_client_lock = RLock()
_clients = {}


def _persistent_client(path):
    key = str(path)
    with _client_lock:
        client = _clients.get(key)
        if client is None:
            client = chromadb.PersistentClient(
                path=key,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            _clients[key] = client
        return client


def close_chroma_client(path):
    """Close one cached client; used by shutdown and isolated tests."""
    key = str(path)
    with _client_lock:
        client = _clients.pop(key, None)
    if client is not None:
        client.close()


def close_all_chroma_clients():
    with _client_lock:
        clients = list(_clients.values())
        _clients.clear()
    for client in clients:
        client.close()


atexit.register(close_all_chroma_clients)


def get_collection():
    client = _persistent_client(settings.CHROMA_PERSIST_DIRECTORY)
    metadata = {'hnsw:space': 'cosine'}
    if settings.EMBEDDING_PROVIDER == 'google':
        metadata.update({
            'embedding_provider': settings.EMBEDDING_PROVIDER,
            'embedding_model': settings.EMBEDDING_MODEL,
            'embedding_dimensions': settings.EMBEDDING_DIMENSIONS or 3072,
        })
    collection = client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata=metadata,
    )
    _validate_collection_profile(collection)
    return collection


def _validate_collection_profile(collection):
    if settings.EMBEDDING_PROVIDER != 'google':
        return
    dimensions = settings.EMBEDDING_DIMENSIONS or 3072
    expected = {
        'embedding_provider': 'google',
        'embedding_model': settings.EMBEDDING_MODEL,
        'embedding_dimensions': dimensions,
    }
    actual = collection.metadata or {}
    if any(actual.get(key) != value for key, value in expected.items()):
        raise ImproperlyConfigured(
            'This Chroma collection does not match the configured Gemini embedding profile. '
            'Choose a new CHROMA_COLLECTION_NAME and re-index submissions.'
        )
    existing_dimensions = getattr(collection, 'dimension', None)
    if existing_dimensions is not None and existing_dimensions != dimensions:
        raise ImproperlyConfigured(
            'This Chroma collection has a different embedding dimension. '
            'Choose a new CHROMA_COLLECTION_NAME and re-index submissions.'
        )


def _validate_vector_dimensions(collection, vectors):
    if not vectors:
        raise ValueError('Embedding provider returned no vectors.')
    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1 or 0 in dimensions:
        raise ValueError('Embedding provider returned inconsistent vector dimensions.')
    dimension = next(iter(dimensions))
    configured = settings.EMBEDDING_DIMENSIONS
    if configured and dimension != configured:
        raise ValueError('Embedding provider returned vectors with an unexpected dimension.')
    existing = getattr(collection, 'dimension', None)
    if existing is not None and dimension != existing:
        raise ImproperlyConfigured(
            'The embedding dimension does not match this Chroma collection. '
            'Use a separate collection and re-index before changing embedding providers.'
        )


def has_indexed_commit(submission, commit_hash):
    result = get_collection().get(
        where={'$and': [
            {'submission_id': str(submission.id)},
            {'commit_hash': commit_hash},
        ]},
        include=['metadatas'],
    )
    return bool(result.get('ids'))


def index_chunks(submission, commit_hash, chunks):
    collection = get_collection()
    existing = collection.get(
        where={'$and': [
            {'submission_id': str(submission.id)},
            {'commit_hash': commit_hash},
        ]},
        include=['metadatas'],
    )
    if existing.get('ids'):
        return len(existing['ids']), True
    if not chunks:
        raise ValueError('No readable source or PDF text was found to index.')

    vectors = get_embedding_provider().embed_documents([chunk.content for chunk in chunks])
    if len(vectors) != len(chunks) or any(not vector for vector in vectors):
        raise ValueError('Embedding provider returned no vector for one or more chunks.')
    _validate_vector_dimensions(collection, vectors)
    ids, documents, metadatas = [], [], []
    for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
        source_key = f"{chunk.metadata.get('source_type')}:{chunk.metadata.get('file_path')}:{chunk.metadata.get('page', '')}:{index}"
        identifier = hashlib.sha256(f'{submission.id}:{commit_hash}:{source_key}'.encode()).hexdigest()
        metadata = {
            'submission_id': str(submission.id),
            'commit_hash': commit_hash,
            **chunk.metadata,
        }
        ids.append(identifier)
        documents.append(chunk.content)
        metadatas.append(metadata)
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=vectors)
    # Keep the persistent index bounded to the currently selected repository commit.
    collection.delete(where={
        '$and': [
            {'submission_id': str(submission.id)},
            {'commit_hash': {'$ne': commit_hash}},
        ],
    })
    return len(ids), False


def retrieve_chunks(submission, query, *, source_type=None, limit=5):
    if not submission.indexed_commit_hash or not query or not query.strip():
        return []
    where = [
        {'submission_id': str(submission.id)},
        {'commit_hash': submission.indexed_commit_hash},
    ]
    if source_type:
        if source_type not in {'CODE', 'PDF'}:
            raise ValueError('source_type must be CODE or PDF.')
        where.append({'source_type': source_type})
    collection = get_collection()
    provider = get_embedding_provider()
    if hasattr(provider, 'embed_query'):
        query_vectors = provider.embed_query(query.strip(), source_type=source_type)
    else:
        query_vectors = provider.embed_documents([query.strip()])
    _validate_vector_dimensions(collection, query_vectors)
    result = collection.query(
        query_embeddings=query_vectors,
        n_results=max(1, min(int(limit), 20)),
        where={'$and': where},
        include=['documents', 'metadatas', 'distances'],
    )
    documents = (result.get('documents') or [[]])[0]
    metadatas = (result.get('metadatas') or [[]])[0]
    distances = (result.get('distances') or [[]])[0]
    return [
        {'content': content, 'metadata': metadata, 'distance': distance}
        for content, metadata, distance in zip(documents, metadatas, distances)
    ]
