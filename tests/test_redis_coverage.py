"""
Тесты для полного покрытия services/redis.py
"""
import json
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
import redis.asyncio as aioredis
from redis.asyncio import Redis

from services.redis import (
    RedisService,
    close_redis,
    init_redis,
    redis,
)


class TestRedisServiceInitialization:
    """Тесты инициализации Redis сервиса"""

    def test_redis_service_init_with_url(self):
        """Тест инициализации с URL"""
        service = RedisService("redis://localhost:6379")
        assert service._redis_url == "redis://localhost:6379"
        assert service._is_available is True

    def test_redis_service_init_without_aioredis(self):
        """Тест инициализации без aioredis"""
        with patch("services.redis.aioredis", None):
            service = RedisService()
            assert service._is_available is False

    def test_redis_service_default_url(self):
        """Тест инициализации с дефолтным URL"""
        service = RedisService()
        assert service._redis_url is not None

    def test_is_connected_property(self):
        """Тест свойства is_connected"""
        service = RedisService()
        assert service.is_connected is False

        service._client = Mock()
        service._is_available = True
        assert service.is_connected is True

        service._is_available = False
        assert service.is_connected is False


class TestRedisConnectionManagement:
    """Тесты управления соединениями Redis"""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Тест успешного подключения"""
        service = RedisService()

        with patch("services.redis.aioredis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_from_url.return_value = mock_client

            await service.connect()

            assert service._client is not None
            assert service.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Тест неудачного подключения"""
        service = RedisService()

        with patch("services.redis.aioredis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection failed")

            await service.connect()

            assert service._client is None
            assert service.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_without_aioredis(self):
        """Тест подключения без aioredis"""
        with patch("services.redis.aioredis", None):
            service = RedisService()
            await service.connect()
            assert service._client is None

    @pytest.mark.asyncio
    async def test_connect_existing_client(self):
        """Тест подключения с существующим клиентом"""
        service = RedisService()
        mock_existing_client = AsyncMock()
        service._client = mock_existing_client

        with patch("services.redis.aioredis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_from_url.return_value = mock_client

            await service.connect()

            # Старый клиент должен быть закрыт
            mock_existing_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Тест отключения"""
        service = RedisService()
        mock_client = AsyncMock()
        service._client = mock_client

        await service.close()

        mock_client.close.assert_called_once()
        assert service._client is None

    @pytest.mark.asyncio
    async def test_disconnect_no_client(self):
        """Тест отключения без клиента"""
        service = RedisService()
        service._client = None

        # Не должно вызывать ошибку
        await service.close()


class TestRedisCommandExecution:
    """Тесты выполнения команд Redis"""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Тест успешного выполнения команды"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        mock_method = AsyncMock(return_value="test_result")
        service._client.test_command = mock_method

        result = await service.execute("test_command", "arg1", "arg2")

        assert result == "test_result"
        mock_method.assert_called_once_with("arg1", "arg2")

    @pytest.mark.asyncio
    async def test_execute_without_aioredis(self):
        """Тест выполнения команды без aioredis"""
        with patch("services.redis.aioredis", None):
            service = RedisService()
            result = await service.execute("test_command")
            assert result is None

    @pytest.mark.asyncio
    async def test_execute_not_connected(self):
        """Тест выполнения команды без подключения"""
        service = RedisService()
        service._is_available = True

        with patch.object(service, "connect") as mock_connect:
            mock_connect.return_value = None
            service._client = None

            result = await service.execute("test_command")
            assert result is None

    @pytest.mark.asyncio
    async def test_execute_unknown_command(self):
        """Тест выполнения неизвестной команды"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        # Убираем все методы из клиента
        service._client.__dict__.clear()

        result = await service.execute("unknown_command")
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_connection_error(self):
        """Тест выполнения команды с ошибкой соединения"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        mock_method = AsyncMock(side_effect=ConnectionError("Connection lost"))
        service._client.test_command = mock_method

        with patch.object(service, "connect") as mock_connect:
            mock_connect.return_value = None

            result = await service.execute("test_command")
            assert result is None

    @pytest.mark.asyncio
    async def test_execute_retry_success(self):
        """Тест успешного повтора команды"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        # Первый вызов падает, второй успешен
        mock_method = AsyncMock(side_effect=[ConnectionError("Connection lost"), "success"])
        service._client.test_command = mock_method

        with patch.object(service, 'connect') as mock_connect:
            mock_connect.return_value = True

            result = await service.execute("test_command")
            assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_retry_failure(self):
        """Тест неудачного повтора команды"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        mock_method = AsyncMock(side_effect=ConnectionError("Connection lost"))
        service._client.test_command = mock_method

        with patch.object(service, "connect") as mock_connect:
            mock_connect.return_value = None

            result = await service.execute("test_command")
            assert result is None

    @pytest.mark.asyncio
    async def test_execute_general_exception(self):
        """Тест общего исключения при выполнении команды"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        mock_method = AsyncMock(side_effect=Exception("General error"))
        service._client.test_command = mock_method

        result = await service.execute("test_command")
        assert result is None


class TestRedisBasicOperations:
    """Тесты базовых операций Redis"""

    @pytest.mark.asyncio
    async def test_get(self):
        """Тест операции GET"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.get = AsyncMock(return_value="test_value")

        result = await service.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set(self):
        """Тест операции SET"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.set = AsyncMock(return_value=True)

        result = await service.set("test_key", "test_value")
        assert result is True

    @pytest.mark.asyncio
    async def test_set_with_expiration(self):
        """Тест операции SET с истечением"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.setex = AsyncMock(return_value=True)

        result = await service.set("test_key", "test_value", ex=3600)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete(self):
        """Тест операции DELETE"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.delete = AsyncMock(return_value=2)

        result = await service.delete("key1", "key2")
        assert result == 2

    @pytest.mark.asyncio
    async def test_delete_none_result(self):
        """Тест операции DELETE с None результатом"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.delete = AsyncMock(return_value=None)

        result = await service.delete("key1")
        assert result == 0

    @pytest.mark.asyncio
    async def test_exists(self):
        """Тест операции EXISTS"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.exists = AsyncMock(return_value=1)

        result = await service.exists("test_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Тест операции EXISTS для несуществующего ключа"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.exists = AsyncMock(return_value=0)

        result = await service.exists("test_key")
        assert result is False


class TestRedisHashOperations:
    """Тесты операций с хешами"""

    @pytest.mark.asyncio
    async def test_hset(self):
        """Тест операции HSET"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.hset = AsyncMock(return_value=1)

        await service.hset("test_hash", "field", "value")
        service._client.hset.assert_called_once_with("test_hash", "field", "value")

    @pytest.mark.asyncio
    async def test_hget(self):
        """Тест операции HGET"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.hget = AsyncMock(return_value="test_value")

        result = await service.hget("test_hash", "field")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_hgetall(self):
        """Тест операции HGETALL"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.hgetall = AsyncMock(return_value={"field1": "value1", "field2": "value2"})

        result = await service.hgetall("test_hash")
        assert result == {"field1": "value1", "field2": "value2"}

    @pytest.mark.asyncio
    async def test_hgetall_none_result(self):
        """Тест операции HGETALL с None результатом"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.hgetall = AsyncMock(return_value=None)

        result = await service.hgetall("test_hash")
        assert result == {}


class TestRedisSetOperations:
    """Тесты операций с множествами"""

    @pytest.mark.asyncio
    async def test_smembers(self):
        """Тест операции SMEMBERS"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        # Симулируем байтовые данные
        service._client.smembers = AsyncMock(return_value=[b"member1", b"member2"])

        result = await service.smembers("test_set")
        assert result == {"member1", "member2"}

    @pytest.mark.asyncio
    async def test_smembers_string_data(self):
        """Тест операции SMEMBERS со строковыми данными"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.smembers = AsyncMock(return_value=["member1", "member2"])

        result = await service.smembers("test_set")
        assert result == {"member1", "member2"}

    @pytest.mark.asyncio
    async def test_smembers_none_result(self):
        """Тест операции SMEMBERS с None результатом"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.smembers = AsyncMock(return_value=None)

        result = await service.smembers("test_set")
        assert result == set()

    @pytest.mark.asyncio
    async def test_smembers_exception(self):
        """Тест операции SMEMBERS с исключением"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.smembers = AsyncMock(side_effect=Exception("Redis error"))

        result = await service.smembers("test_set")
        assert result == set()

    @pytest.mark.asyncio
    async def test_smembers_not_connected(self):
        """Тест операции SMEMBERS без подключения"""
        service = RedisService()
        service._client = None
        service._is_available = True

        result = await service.smembers("test_set")
        assert result == set()

    @pytest.mark.asyncio
    async def test_sadd(self):
        """Тест операции SADD"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.sadd = AsyncMock(return_value=2)

        result = await service.sadd("test_set", "member1", "member2")
        assert result == 2

    @pytest.mark.asyncio
    async def test_sadd_none_result(self):
        """Тест операции SADD с None результатом"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.sadd = AsyncMock(return_value=None)

        result = await service.sadd("test_set", "member1")
        assert result == 0

    @pytest.mark.asyncio
    async def test_srem(self):
        """Тест операции SREM"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.srem = AsyncMock(return_value=1)

        result = await service.srem("test_set", "member1")
        assert result == 1

    @pytest.mark.asyncio
    async def test_srem_none_result(self):
        """Тест операции SREM с None результатом"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.srem = AsyncMock(return_value=None)

        result = await service.srem("test_set", "member1")
        assert result == 0


class TestRedisUtilityOperations:
    """Тесты утилитарных операций Redis"""

    @pytest.mark.asyncio
    async def test_expire(self):
        """Тест операции EXPIRE"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.expire = AsyncMock(return_value=True)

        result = await service.expire("test_key", 3600)
        assert result is True

    @pytest.mark.asyncio
    async def test_expire_false(self):
        """Тест операции EXPIRE с False результатом"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.expire = AsyncMock(return_value=False)

        result = await service.expire("test_key", 3600)
        assert result is False

    @pytest.mark.asyncio
    async def test_keys(self):
        """Тест операции KEYS"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.keys = AsyncMock(return_value=["key1", "key2"])

        result = await service.keys("test:*")
        assert result == ["key1", "key2"]

    @pytest.mark.asyncio
    async def test_keys_none_result(self):
        """Тест операции KEYS с None результатом"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.keys = AsyncMock(return_value=None)

        result = await service.keys("test:*")
        assert result == []

    @pytest.mark.asyncio
    async def test_ping(self):
        """Тест операции PING"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.ping = AsyncMock(return_value=True)

        result = await service.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_ping_not_connected(self):
        """Тест операции PING без подключения"""
        service = RedisService()
        service._client = None
        service._is_available = True

        result = await service.ping()
        assert result is False

    @pytest.mark.asyncio
    async def test_ping_exception(self):
        """Тест операции PING с исключением"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.ping = AsyncMock(side_effect=Exception("Redis error"))

        result = await service.ping()
        assert result is False


class TestRedisSerialization:
    """Тесты сериализации данных"""

    @pytest.mark.asyncio
    async def test_serialize_and_set_string(self):
        """Тест сериализации и сохранения строки"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.set = AsyncMock(return_value=True)

        result = await service.serialize_and_set("test_key", "test_value")
        assert result is True

    @pytest.mark.asyncio
    async def test_serialize_and_set_bytes(self):
        """Тест сериализации и сохранения байтов"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.set = AsyncMock(return_value=True)

        result = await service.serialize_and_set("test_key", b"test_value")
        assert result is True

    @pytest.mark.asyncio
    async def test_serialize_and_set_dict(self):
        """Тест сериализации и сохранения словаря"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.set = AsyncMock(return_value=True)

        data = {"key": "value", "number": 42}
        result = await service.serialize_and_set("test_key", data)
        assert result is True

    @pytest.mark.asyncio
    async def test_serialize_and_set_exception(self):
        """Тест сериализации с исключением"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.set = AsyncMock(side_effect=Exception("Redis error"))

        result = await service.serialize_and_set("test_key", "test_value")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_and_deserialize_success(self):
        """Тест успешного получения и десериализации"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.get = AsyncMock(return_value=b'{"key": "value"}')

        result = await service.get_and_deserialize("test_key")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_and_deserialize_string(self):
        """Тест получения и десериализации строки"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.get = AsyncMock(return_value='{"key": "value"}')

        result = await service.get_and_deserialize("test_key")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_and_deserialize_none(self):
        """Тест получения и десериализации None"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.get = AsyncMock(return_value=None)

        result = await service.get_and_deserialize("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_and_deserialize_exception(self):
        """Тест получения и десериализации с исключением"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.get = AsyncMock(return_value=b"invalid json")

        result = await service.get_and_deserialize("test_key")
        assert result is None


class TestRedisPipeline:
    """Тесты pipeline операций"""

    @pytest.mark.asyncio
    async def test_pipeline_property(self):
        """Тест свойства pipeline"""
        service = RedisService()
        service._client = Mock()
        service._is_available = True

        mock_pipeline = Mock()
        service._client.pipeline.return_value = mock_pipeline

        result = service.pipeline()
        assert result == mock_pipeline

    @pytest.mark.asyncio
    async def test_pipeline_not_connected(self):
        """Тест pipeline без подключения"""
        service = RedisService()
        service._client = None

        result = service.pipeline()
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_pipeline_success(self):
        """Тест успешного выполнения pipeline"""
        service = RedisService()
        service._client = Mock()
        service._is_available = True

        mock_pipeline = Mock()
        mock_pipeline.execute = AsyncMock(return_value=["result1", "result2"])
        service._client.pipeline.return_value = mock_pipeline

        # Добавляем методы в pipeline
        mock_pipeline.set = Mock()
        mock_pipeline.get = Mock()

        commands = [
            ("set", ("key1", "value1")),
            ("get", ("key2",)),
        ]

        result = await service.execute_pipeline(commands)
        assert result == ["result1", "result2"]

    @pytest.mark.asyncio
    async def test_execute_pipeline_not_connected(self):
        """Тест выполнения pipeline без подключения"""
        service = RedisService()
        service._client = None
        service._is_available = True

        commands = [("set", ("key1", "value1"))]

        result = await service.execute_pipeline(commands)
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_pipeline_failed_creation(self):
        """Тест выполнения pipeline с неудачным созданием"""
        service = RedisService()
        service._client = Mock()
        service._is_available = True

        service._client.pipeline.return_value = None

        commands = [("set", ("key1", "value1"))]

        result = await service.execute_pipeline(commands)
        assert result == []

    @pytest.mark.asyncio
    async def test_execute_pipeline_unknown_command(self):
        """Тест выполнения pipeline с неизвестной командой"""
        service = RedisService()
        service._client = Mock()
        service._is_available = True

        mock_pipeline = Mock()
        mock_pipeline.execute = AsyncMock(return_value=["result1"])
        service._client.pipeline.return_value = mock_pipeline

        # Добавляем только set метод в pipeline
        mock_pipeline.set = Mock()

        commands = [
            ("set", ("key1", "value1")),
            ("unknown_command", ("arg1",)),
        ]

        result = await service.execute_pipeline(commands)
        assert result == ["result1"]

    @pytest.mark.asyncio
    async def test_execute_pipeline_exception(self):
        """Тест выполнения pipeline с исключением"""
        service = RedisService()
        service._client = Mock()
        service._is_available = True

        mock_pipeline = Mock()
        mock_pipeline.execute = AsyncMock(side_effect=Exception("Pipeline error"))
        service._client.pipeline.return_value = mock_pipeline

        commands = [("set", ("key1", "value1"))]

        result = await service.execute_pipeline(commands)
        assert result == []


class TestRedisPublish:
    """Тесты публикации сообщений"""

    @pytest.mark.asyncio
    async def test_publish_success(self):
        """Тест успешной публикации"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.publish = AsyncMock(return_value=1)

        await service.publish("test_channel", "test_message")
        service._client.publish.assert_called_once_with("test_channel", "test_message")

    @pytest.mark.asyncio
    async def test_publish_not_connected(self):
        """Тест публикации без подключения"""
        service = RedisService()
        service._client = None
        service._is_available = True

        # Не должно вызывать ошибку
        await service.publish("test_channel", "test_message")

    @pytest.mark.asyncio
    async def test_publish_exception(self):
        """Тест публикации с исключением"""
        service = RedisService()
        service._client = AsyncMock()
        service._is_available = True

        service._client.publish = AsyncMock(side_effect=Exception("Publish error"))

        # Не должно вызывать ошибку
        await service.publish("test_channel", "test_message")


class TestGlobalRedisFunctions:
    """Тесты глобальных функций Redis"""

    @pytest.mark.asyncio
    async def test_init_redis(self):
        """Тест инициализации глобального Redis"""
        with patch.object(redis, "connect") as mock_connect:
            await init_redis()
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_redis(self):
        """Тест закрытия глобального Redis"""
        with patch.object(redis, "disconnect") as mock_disconnect:
            await close_redis()
            mock_disconnect.assert_called_once()

    def test_global_redis_instance(self):
        """Тест глобального экземпляра Redis"""
        assert redis is not None
        assert isinstance(redis, RedisService)


class TestRedisLogging:
    """Тесты логирования Redis"""

    def test_redis_logger_level(self):
        """Тест уровня логирования Redis"""
        redis_logger = logging.getLogger("redis")
        assert redis_logger.level == logging.WARNING


class TestAdditionalRedisCoverage:
    """Дополнительные тесты для покрытия недостающих строк Redis"""

    async def test_connect_exception_handling(self):
        """Test connect with exception during close"""
        service = RedisService()
        mock_client = AsyncMock()
        service._client = mock_client
        mock_client.close.side_effect = Exception("Close error")

        with patch('services.redis.aioredis.from_url') as mock_from_url:
            mock_new_client = AsyncMock()
            mock_from_url.return_value = mock_new_client

            await service.connect()

            # Should handle the exception and continue
            assert service._client is not None

    async def test_disconnect_exception_handling(self):
        """Test disconnect with exception"""
        service = RedisService()
        mock_client = AsyncMock()
        service._client = mock_client
        mock_client.close.side_effect = Exception("Disconnect error")

        # The disconnect method doesn't handle exceptions, so it should raise
        with pytest.raises(Exception, match="Disconnect error"):
            await service.close()

        # Since exception is not handled, client remains unchanged
        assert service._client is mock_client

    async def test_get_and_deserialize_exception(self):
        """Test get_and_deserialize with exception"""
        service = RedisService()

        with patch.object(service, 'get') as mock_get:
            mock_get.return_value = b'invalid json'

            result = await service.get_and_deserialize("test_key")

            assert result is None

    async def test_execute_pipeline_unknown_command_logging(self):
        """Test execute_pipeline with unknown command logging"""
        service = RedisService()
        mock_client = Mock()
        service._client = mock_client

        mock_pipeline = Mock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_pipeline.set = Mock()
        mock_pipeline.get = Mock()

        # Test with unknown command
        commands = [("unknown", ("key",))]

        result = await service.execute_pipeline(commands)

        assert result == []
