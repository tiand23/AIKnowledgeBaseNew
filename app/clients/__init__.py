"""
外部服务客户端
"""
from app.clients.redis_client import redis_client
from app.clients.db_client import db_client
from app.clients.minio_client import minio_client
from app.clients.elasticsearch_client import es_client
from app.clients.kafka_client import kafka_client

__all__ = ['redis_client', 'db_client', 'minio_client', 'es_client', 'kafka_client']

