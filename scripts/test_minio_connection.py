"""
测试 MinIO 连接
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clients.minio_client import minio_client
from app.core.config import settings


def test_minio():
    print("=" * 50)
    print("测试： MinIO 连接")
    print("=" * 50)
    print(f"\n测试：MinIO 端点：{settings.MINIO_ENDPOINT}")
    print(f"测试：访问密钥：{settings.MINIO_ACCESS_KEY}")
    print(f"测试：使用 HTTPS：{settings.MINIO_SECURE}\n")

    try:
        print("测试：正在连接 MinIO...")
        minio_client.connect()

        print("\n测试：执行健康检查...")
        is_healthy = minio_client.health_check()
        
        if is_healthy:
            print("测试：健康检查通过")
        else:
            print("测试：健康检查失败")
            return False

        status = minio_client.get_status()
        print("\n测试：MinIO 状态信息：")
        for key, value in status.items():
            if key != "存储桶列表":
                print(f"  {key}: {value}")
        
        if "存储桶列表" in status and status["存储桶列表"]:
            print(f"  存储桶列表: {', '.join(status['存储桶列表'])}")

        test_bucket = "test-connection-bucket"
        print(f"\n测试：确保存储桶存在：{test_bucket}")
        
        success = minio_client.ensure_bucket(test_bucket)
        if success:
            print(f"测试：存储桶已就绪")
        else:
            print(f"测试：存储桶操作失败")
            return False

        test_object = "test/hello.txt"
        test_content = b"Hello MinIO! This is a test file."
        
        print(f"\n测试：上传测试文件：{test_object}")
        print(f"测试：文件内容：{test_content.decode('utf-8')}")
        
        success = minio_client.upload_bytes(
            bucket_name=test_bucket,
            object_name=test_object,
            data=test_content,
            content_type="text/plain"
        )
        
        if success:
            print("测试：文件上传成功")
        else:
            print("测试：文件上传失败")
            return False

        print("\n测试：检查文件是否存在...")
        exists = minio_client.file_exists(test_bucket, test_object)
        
        if exists:
            print("测试：文件存在确认")
        else:
            print("测试：文件不存在")
            return False

        print("\n测试：获取文件信息...")
        file_info = minio_client.get_file_info(test_bucket, test_object)
        
        if file_info:
            print("测试：文件信息：")
            print(f"  文件名：{file_info['name']}")
            print(f"  大小：{file_info['size']} 字节")
            print(f"  类型：{file_info['content_type']}")
            print(f"  最后修改：{file_info['last_modified']}")
        else:
            print("测试：获取文件信息失败")

        print("\n测试：下载文件...")
        downloaded_data = minio_client.download_file(test_bucket, test_object)
        
        if downloaded_data:
            print(f"测试：文件下载成功")
            print(f"测试：下载内容：{downloaded_data.decode('utf-8')}")
            
            if downloaded_data == test_content:
                print("测试：文件内容验证通过")
            else:
                print("测试：文件内容不匹配")
                return False
        else:
            print("测试：文件下载失败")
            return False

        print("\n测试：生成预签名 URL...")
        from datetime import timedelta
        url = minio_client.get_file_url(
            bucket_name=test_bucket,
            object_name=test_object,
            expires=timedelta(hours=1)
        )
        
        if url:
            print(f"测试：预签名 URL 生成成功")
            print(f"测试：URL（前80字符）：{url[:80]}...")
        else:
            print("测试：预签名 URL 生成失败")

        print("\n测试：列出存储桶中的文件...")
        files = minio_client.list_files(test_bucket, prefix="test/")
        
        if files:
            print(f"测试：找到 {len(files)} 个文件：")
            for file in files:
                print(f"  - {file['name']} ({file['size']} 字节)")
        else:
            print("测试：未找到文件")

        print("\n测试：清理测试数据...")
        success = minio_client.delete_file(test_bucket, test_object)
        
        if success:
            print("测试：测试文件已删除")
        else:
            print("测试：删除测试文件失败")

        exists = minio_client.file_exists(test_bucket, test_object)
        if not exists:
            print("测试：文件删除确认")
        else:
            print("测试：文件仍然存在")

        print("\n" + "=" * 50)
        print("测试：MinIO 连接成功！")
        print("=" * 50)
        print("测试：所有功能测试通过")

        minio_client.close()
        print("\n测试：连接已正常关闭")
        return True

    except Exception as e:
        print("\n" + "=" * 50)
        print("测试：MinIO 连接失败！")
        print("=" * 50)
        print(f"测试：错误类型: {type(e).__name__}")
        print(f"测试：错误信息: {str(e)}")
        
        try:
            minio_client.close()
        except:
            pass
        
        return False


if __name__ == "__main__":
    print("\n测试：启动 MinIO 连接测试...\n")
    success = test_minio()

    if success:
        print("\n测试：所有测试通过！")
        sys.exit(0)
    else:
        print("\n测试：提示排查问题后重试")
        sys.exit(1)

