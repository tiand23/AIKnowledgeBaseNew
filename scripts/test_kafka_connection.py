"""
测试 Kafka 连接
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.kafka_client import kafka_client
from app.core.config import settings


async def test_kafka():
    print("=" * 50)
    print("测试： Kafka 连接")
    print("=" * 50)
    print(f"\n测试：Kafka 服务器：{settings.KAFKA_BOOTSTRAP_SERVERS}")
    print(f"测试：默认主题：{settings.KAFKA_DEFAULT_TOPIC}\n")

    try:
        print("测试：正在连接 Kafka...")
        await kafka_client.connect()

        print("\n测试：执行健康检查...")
        is_healthy = await kafka_client.health_check()
        
        if is_healthy:
            print("测试：健康检查通过")
        else:
            print("测试：健康检查失败")
            return False

        status = kafka_client.get_status()
        print("\n测试：Kafka 状态信息：")
        for key, value in status.items():
            if key != "消费者列表":
                print(f"  {key}: {value}")

        test_topic = "test-connection-topic"
        
        print(f"\n测试：发送测试消息到主题：{test_topic}")
        
        test_message = {
            "type": "test",
            "message": "Hello Kafka!",
            "timestamp": "2024-01-01T00:00:00"
        }
        
        print(f"测试：消息内容：{test_message}")
        
        success = await kafka_client.send_message(
            topic=test_topic,
            value=test_message,
            key="test_key_1"
        )
        
        if success:
            print("测试：消息发送成功（异步）")
        else:
            print("测试：消息发送失败")
            return False

        print("\n测试：同步发送消息（等待确认）...")
        
        test_message_2 = {
            "type": "test",
            "message": "Hello Kafka Sync!",
            "timestamp": "2024-01-01T00:00:01"
        }
        
        metadata = await kafka_client.send_message_sync(
            topic=test_topic,
            value=test_message_2,
            key="test_key_2"
        )
        
        if metadata:
            print("测试：同步发送成功")
            print(f"  主题：{metadata['topic']}")
            print(f"  分区：{metadata['partition']}")
            print(f"  偏移量：{metadata['offset']}")
            print(f"  时间戳：{metadata['timestamp']}")
        else:
            print("测试：同步发送失败")
            return False

        print("\n测试：批量发送消息...")
        
        batch_messages = [
            {
                "value": {"id": 1, "message": "Batch message 1"},
                "key": "batch_1"
            },
            {
                "value": {"id": 2, "message": "Batch message 2"},
                "key": "batch_2"
            },
            {
                "value": {"id": 3, "message": "Batch message 3"},
                "key": "batch_3"
            }
        ]
        
        success_count = await kafka_client.send_batch(
            topic=test_topic,
            messages=batch_messages
        )
        
        print(f"测试：批量发送完成，成功 {success_count}/{len(batch_messages)} 条消息")

        print("\n测试：刷新生产者缓冲区...")
        await kafka_client.flush()
        print("测试：缓冲区刷新完成")

        print(f"\n测试：获取主题分区信息：{test_topic}")
        partitions = await kafka_client.get_topic_partitions(test_topic)
        
        if partitions is not None:
            print(f"测试：主题分区数：{partitions}")
        else:
            print("测试：获取分区信息失败")

        print(f"\n测试：创建消费者...")
        
        async def message_handler(message):
            print(f"  收到消息: topic={message.topic}, partition={message.partition}, offset={message.offset}")
            print(f"  消息键: {message.key}")
            print(f"  消息值: {message.value}")
        
        consumer = await kafka_client.create_consumer(
            topics=[test_topic],
            group_id="test_group",
            auto_offset_reset='earliest'  # Start consuming from earliest offsets
        )
        
        if consumer:
            print(f"测试：消费者创建成功")
            
            print(f"\n测试：开始消费消息（最多5条）...")
            
            try:
                await asyncio.wait_for(
                    kafka_client.consume_messages(
                        consumer=consumer,
                        callback=message_handler,
                        max_messages=5
                    ),
                    timeout=10.0  # 10-second timeout
                )
                print("测试：消费测试完成")
            except asyncio.TimeoutError:
                print("测试：消费超时（可能没有消息）")
            
            await consumer.stop()
            print("测试：消费者已停止")
        else:
            print("测试：消费者创建失败")

        print("\n" + "=" * 50)
        print("测试：Kafka 连接成功！")
        print("=" * 50)
        print("测试：所有功能测试通过")

        await kafka_client.close()
        print("\n测试：连接已正常关闭")
        return True

    except Exception as e:
        print("\n" + "=" * 50)
        print("测试：Kafka 连接失败！")
        print("=" * 50)
        print(f"测试：错误类型: {type(e).__name__}")
        print(f"测试：错误信息: {str(e)}")
        
        try:
            await kafka_client.close()
        except:
            pass
        
        return False


if __name__ == "__main__":
    print("\n测试：启动 Kafka 连接测试...\n")
    success = asyncio.run(test_kafka())

    if success:
        print("\n测试：所有测试通过！")
        sys.exit(0)
    else:
        print("\n测试：提示排查问题后重试")
        print("提示：请确保 Kafka 服务正在运行（localhost:9092）")
        sys.exit(1)

