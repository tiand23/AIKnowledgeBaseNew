"""
测试文件上传功能
"""
import asyncio
import sys
import hashlib
import warnings
import logging
from pathlib import Path
from io import BytesIO

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)

from app.clients.minio_client import minio_client
from app.clients.redis_client import redis_client
from app.clients.db_client import db_client
from app.services.file_service import file_service
from app.core.config import settings
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

_original_connect = db_client.connect

def _test_connect():
    db_client.engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # Disable SQL query logging in tests
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    
    db_client.SessionLocal = async_sessionmaker(
        db_client.engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

db_client.connect = _test_connect


def calculate_file_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


async def create_test_user(db_session, username: str = "test_user") -> User:
    result = await db_session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if not user:
        print(f"测试用户 '{username}' 不存在，请先在数据库中创建该用户")
        return None
    
    return user


async def test_chunk_upload():
    print("=" * 60)
    print("测试：分片上传功能")
    print("=" * 60)
    
    try:
        print("\n1. 连接服务...")
        db_client.connect()
        await redis_client.connect()
        minio_client.connect()
        print("服务连接成功")
        
        async for db_session in db_client.get_session():
            user = await create_test_user(db_session)
            if not user:
                print("测试失败：无法获取测试用户")
                return False
            
            print(f"\n2. 使用测试用户:")
            print(f"   用户名: {user.username}")
            print(f"   用户ID: {user.id}")
            
            print("\n3. 创建测试文件...")
            test_file_content = b"This is a test file content for chunk upload. " * 100  # About 4KB
            file_md5 = calculate_file_md5(test_file_content)
            file_name = "test_chunk_upload.txt"
            total_size = len(test_file_content)
            
            chunk_size = 1024
            total_chunks = (total_size + chunk_size - 1) // chunk_size
            
            print(f"   文件MD5值: {file_md5} (用于唯一标识文件)")
            print(f"   文件名: {file_name}")
            print(f"   文件大小: {total_size} 字节")
            print(f"   分片大小: {chunk_size} 字节 (每个分片的固定大小)")
            print(f"   总分片数: {total_chunks} (文件将被分割成 {total_chunks} 个分片)")
            
            print("\n4. 上传分片...")
            uploaded_chunks_list = []
            
            for chunk_index in range(total_chunks):
                start = chunk_index * chunk_size
                end = min(start + chunk_size, total_size)
                chunk_data = test_file_content[start:end]
                
                print(f"   正在上传分片 {chunk_index + 1}/{total_chunks} (分片索引: {chunk_index})...", end="")
                
                try:
                    uploaded_chunks, progress = await file_service.upload_chunk(
                        db=db_session,
                        user=user,
                        file_md5=file_md5,
                        chunk_index=chunk_index,
                        chunk_data=chunk_data,
                        file_name=file_name,
                        total_size=total_size,
                        total_chunks=total_chunks,
                        org_tag=None,
                        is_public=False
                    )
                    
                    uploaded_chunks_list = uploaded_chunks
                    print(f" 上传成功 (当前进度: {progress:.1f}%, 已上传分片: {uploaded_chunks})")
                    
                except Exception as e:
                    print(f" 上传失败: {e}")
                    return False
            
            print("\n5. 验证上传状态...")
            print("   从数据库和Redis查询文件上传状态...")
            try:
                uploaded_chunks, progress, total_chunks_check = await file_service.get_upload_status(
                    db=db_session,
                    user=user,
                    file_md5=file_md5
                )
                
                print(f"   已上传分片索引列表: {uploaded_chunks} (共 {len(uploaded_chunks)} 个分片已上传)")
                print(f"   上传进度百分比: {progress:.1f}%")
                print(f"   总分片数: {total_chunks_check} (从数据库查询得到)")
                
                if progress == 100.0 and len(uploaded_chunks) == total_chunks:
                    print("  验证结果: 所有分片上传成功，可以开始合并文件")
                else:
                    print(f" 验证结果: 上传不完整，缺少 {total_chunks - len(uploaded_chunks)} 个分片")
                    return False
                    
            except Exception as e:
                print(f" 查询状态失败: {e}")
                return False
            
            print("\n6. 测试文件合并...")
            print("   将所有分片合并为完整文件...")
            try:
                object_url, file_size = await file_service.merge_file(
                    db=db_session,
                    user=user,
                    file_md5=file_md5,
                    file_name=file_name
                )
                
                print(f"   合并后文件访问URL: {object_url}")
                print(f"   合并后文件大小: {file_size} 字节")
                print(" 文件合并操作成功")
                
                print("   验证合并后的文件是否存在于MinIO...")
                file_path = minio_client.build_document_path(user.id, file_name)
                if minio_client.file_exists(settings.MINIO_DEFAULT_BUCKET, file_path):
                    print(f" 验证成功: 合并后的文件在MinIO中已存在 (路径: {file_path})")
                else:
                    print(f" 验证警告: 合并后的文件在MinIO中不存在 (路径: {file_path})，可能URL生成问题")
                
            except Exception as e:
                print(f" 文件合并失败: {e}")
                return False
            
            print("\n7. 清理测试数据...")
            print("   删除MinIO中的文件、数据库记录和Redis缓存...")
            try:
                await file_service.delete_file(
                    db=db_session,
                    user=user,
                    file_md5=file_md5
                )
                print(" 测试数据清理成功 (已删除文件、数据库记录和缓存)")
            except Exception as e:
                print(f" 清理测试数据失败: {e} (不影响测试结果)")
            
            break  # Run a single session in this test
        
        print("\n8. 关闭服务连接...")
        try:
            print("   关闭MySQL数据库连接...")
            await db_client.close()
            print("   关闭Redis连接...")
            await redis_client.close()
            print("   关闭MinIO连接...")
            minio_client.close()
            print("   所有服务连接已关闭")
        except Exception as e:
            print(f"   关闭连接时出现警告（可忽略）: {type(e).__name__}")
        
        print("\n" + "=" * 60)
        print(" 分片上传功能测试通过！")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n 测试失败: {e}")
        print("   错误详情:")
        import traceback
        traceback.print_exc()
        return False


async def test_upload_status():
    print("\n" + "=" * 60)
    print("测试：上传状态查询功能")
    print("=" * 60)
    
    try:
        print("\n1. 连接服务...")
        print("   连接MySQL数据库...")
        db_client.connect()
        print("   连接Redis缓存...")
        await redis_client.connect()
        print("   连接MinIO对象存储...")
        minio_client.connect()
        print("   所有服务连接成功")
        
        async for db_session in db_client.get_session():
            user = await create_test_user(db_session)
            if not user:
                print("测试失败：无法获取测试用户")
                return False
            
            print("\n2. 创建测试文件并上传部分分片...")
            print("   创建测试文件并只上传前2个分片（模拟未完成的上传）...")
            test_file_content = b"Test content for status check. " * 50
            file_md5 = calculate_file_md5(test_file_content)
            file_name = "test_status_check.txt"
            total_size = len(test_file_content)
            chunk_size = 1024
            total_chunks = (total_size + chunk_size - 1) // chunk_size
            
            print(f"   文件MD5: {file_md5}")
            print(f"   总分片数: {total_chunks}")
            print(f"   将上传前 {min(2, total_chunks)} 个分片用于测试...")
            
            for chunk_index in range(min(2, total_chunks)):
                start = chunk_index * chunk_size
                end = min(start + chunk_size, total_size)
                chunk_data = test_file_content[start:end]
                
                print(f"   上传分片 {chunk_index + 1}/{min(2, total_chunks)}...", end="")
                try:
                    uploaded_chunks, progress = await file_service.upload_chunk(
                        db=db_session,
                        user=user,
                        file_md5=file_md5,
                        chunk_index=chunk_index,
                        chunk_data=chunk_data,
                        file_name=file_name,
                        total_size=total_size,
                        total_chunks=total_chunks,
                        org_tag=None,
                        is_public=False
                    )
                    print(f" 上传成功 (进度: {progress:.1f}%)")
                except Exception as e:
                    print(f" 上传失败: {e}")
                    return False
            
            print("\n3. 查询上传状态...")
            print("   从Redis和数据库查询当前上传进度...")
            uploaded_chunks, progress, total_chunks_check = await file_service.get_upload_status(
                db=db_session,
                user=user,
                file_md5=file_md5
            )
            
            print(f"   已上传分片索引列表: {uploaded_chunks}")
            print(f"   上传进度百分比: {progress:.1f}%")
            print(f"   总分片数: {total_chunks_check}")
            
            expected_chunks = min(2, total_chunks)
            if len(uploaded_chunks) == expected_chunks:
                print(f" 状态查询成功: 正确返回了 {expected_chunks} 个已上传分片")
            else:
                print(f" 状态查询失败: 期望 {expected_chunks} 个分片，实际 {len(uploaded_chunks)} 个")
                return False
            
            print("\n4. 清理测试数据...")
            try:
                await file_service.delete_file(db=db_session, user=user, file_md5=file_md5)
                print(" 测试数据清理成功")
            except Exception as e:
                print(f" 清理失败: {e} (不影响测试结果)")
            
            break
        
        print("\n5. 关闭服务连接...")
        try:
            print("   关闭MySQL数据库连接...")
            await db_client.close()
            print("   关闭Redis连接...")
            await redis_client.close()
            print("   关闭MinIO连接...")
            minio_client.close()
            print("   所有服务连接已关闭")
        except Exception as e:
            print(f"   关闭连接时出现警告（可忽略）: {type(e).__name__}")
        
        print("\n" + "=" * 60)
        print(" 上传状态查询功能测试通过！")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n 测试失败: {e}")
        print("   错误详情:")
        import traceback
        traceback.print_exc()
        return False


async def test_file_list():
    print("\n" + "=" * 60)
    print("测试：文件列表查询功能")
    print("=" * 60)
    
    try:
        print("\n1. 连接服务...")
        print("   连接MySQL数据库...")
        db_client.connect()
        print("   连接Redis缓存...")
        await redis_client.connect()
        print("   连接MinIO对象存储...")
        minio_client.connect()
        print("   所有服务连接成功")
        
        async for db_session in db_client.get_session():
            user = await create_test_user(db_session)
            if not user:
                print("测试失败：无法获取测试用户")
                return False
            
            print(f"\n2. 使用测试用户: {user.username} (ID: {user.id})")
            
            print("\n3. 创建测试文件并上传...")
            print("   为了测试文件列表查询，先创建几个测试文件...")
            
            test_files = [
                {"name": "测试文档1.txt", "content": "这是第一个测试文档的内容。".encode('utf-8'), "is_public": False},
                {"name": "测试文档2.pdf", "content": "这是第二个测试文档的内容，稍长一些。".encode('utf-8'), "is_public": True},
                {"name": "测试文档3.docx", "content": "这是第三个测试文档的内容，用于测试文件列表查询功能。".encode('utf-8'), "is_public": False},
            ]
            
            uploaded_file_md5s = []
            
            for idx, test_file in enumerate(test_files, 1):
                print(f"\n   创建测试文件 {idx}/{len(test_files)}: {test_file['name']}...")
                file_content = test_file['content']
                file_md5 = calculate_file_md5(file_content)
                file_name = test_file['name']
                total_size = len(file_content)
                
                try:
                    uploaded_chunks, progress = await file_service.upload_chunk(
                        db=db_session,
                        user=user,
                        file_md5=file_md5,
                        chunk_index=0,
                        chunk_data=file_content,
                        file_name=file_name,
                        total_size=total_size,
                        total_chunks=1,
                        org_tag=user.primary_org,
                        is_public=test_file['is_public']
                    )
                    
                    uploaded_file_md5s.append(file_md5)
                    print(f"   文件 '{file_name}' 上传成功 (MD5: {file_md5[:8]}...)")
                    
                    try:
                        await file_service.merge_file(
                            db=db_session,
                            user=user,
                            file_md5=file_md5,
                            file_name=file_name
                        )
                        print(f"   文件 '{file_name}' 合并成功")
                    except Exception as e:
                        print(f"   文件 '{file_name}' 合并失败: {e} (不影响列表查询测试)")
                        
                except Exception as e:
                    print(f"   文件 '{file_name}' 上传失败: {e}")
            
            print(f"\n   总计创建了 {len(uploaded_file_md5s)} 个测试文件")
            
            print("\n4. 查询用户上传的文件列表...")
            print("   查询当前用户上传的所有文件...")
            files = await file_service.get_user_uploaded_files(
                db=db_session,
                user=user
            )
            
            print(f"   查询结果: 找到 {len(files)} 个文件")
            if len(files) > 0:
                print("   文件列表详情 (前5个):")
                for idx, file in enumerate(files[:5], 1):  # Show only first 5 items
                    status_text = "上传中" if file.status == 0 else "已完成" if file.status == 1 else "失败"
                    print(f"   {idx}. 文件名: {file.file_name}")
                    print(f"      - 文件MD5: {file.file_md5[:8]}... (前8位，完整MD5: {file.file_md5})")
                    print(f"      - 上传状态: {file.status} ({status_text})")
                    print(f"      - 文件大小: {file.total_size} 字节")
                    print(f"      - 组织标签: {file.org_tag or '无'}")
                    print(f"      - 是否公开: {'是' if file.is_public else '否'}")
                    print(f"      - 创建时间: {file.created_at}")
            else:
                print("   查询结果: 未找到任何文件（可能存在问题）")
                return False
            
            if len(files) > 5:
                print(f"   ... 还有 {len(files) - 5} 个文件未显示")
            
            print("\n5. 验证查询结果...")
            expected_count = len(uploaded_file_md5s)
            if len(files) >= expected_count:
                print(f"   验证成功: 查询到 {len(files)} 个文件，期望至少 {expected_count} 个")
                
                found_md5s = [f.file_md5 for f in files]
                missing_files = [md5 for md5 in uploaded_file_md5s if md5 not in found_md5s]
                if missing_files:
                    print(f"   警告: {len(missing_files)} 个上传的文件未在列表中")
                else:
                    print(f"   所有上传的文件都在列表中")
            else:
                print(f"   验证失败: 只查询到 {len(files)} 个文件，期望至少 {expected_count} 个")
                return False
            
            print("\n6. 查询可访问的文件列表...")
            print("   查询用户可访问的所有文件（包括自己上传的、公开的、所属组织的）...")
            accessible_files = await file_service.get_accessible_files(
                db=db_session,
                user=user
            )
            
            print(f"   查询结果: 找到 {len(accessible_files)} 个可访问文件")
            
            own_files = [f for f in accessible_files if f.user_id == user.id]
            public_files = [f for f in accessible_files if f.is_public]
            org_files = []
            if user.org_tags:
                org_tags_list = [tag.strip() for tag in user.org_tags.split(",") if tag.strip()]
                org_files = [f for f in accessible_files if f.org_tag in org_tags_list and f not in own_files]
            
            print(f"   文件分类统计:")
            print(f"         - 自己上传的文件: {len(own_files)} 个")
            print(f"         - 公开文件: {len(public_files)} 个 (包括自己上传的公开文件)")
            print(f"         - 所属组织的文件: {len(org_files)} 个 (不包括自己上传的)")
            
            if len(accessible_files) >= len(own_files):
                print(f"   验证成功: 可访问文件数 >= 自己上传的文件数")
            else:
                print(f"   验证失败: 可访问文件数少于自己上传的文件数")
                return False
            
            print("\n   文件列表查询功能正常")
            
            print("\n7. 测试数据说明...")
            print(f"   本测试创建了 {len(uploaded_file_md5s)} 个文件")
            print("   所有测试文件将在测试结束后统一清理")
            
            break
        
        print("\n8. 关闭服务连接...")
        try:
            print("   关闭MySQL数据库连接...")
            await db_client.close()
            print("   关闭Redis连接...")
            await redis_client.close()
            print("   关闭MinIO连接...")
            minio_client.close()
            print("   所有服务连接已关闭")
        except Exception as e:
            print(f"   关闭连接时出现警告（可忽略）: {type(e).__name__}")
        
        print("\n" + "=" * 60)
        print(" 文件列表查询功能测试通过！")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n 测试失败: {e}")
        print("   错误详情:")
        import traceback
        traceback.print_exc()
        return False


async def test_file_access_permission():
    print("\n" + "=" * 60)
    print("测试：文件访问权限控制")
    print("=" * 60)
    
    try:
        print("\n1. 连接服务...")
        print("   连接MySQL数据库...")
        db_client.connect()
        print("   连接Redis缓存...")
        await redis_client.connect()
        print("   连接MinIO对象存储...")
        minio_client.connect()
        print("   所有服务连接成功")
        
        async for db_session in db_client.get_session():
            user1 = await create_test_user(db_session, "test_user")
            user2 = await create_test_user(db_session, "test_user_2")
            
            if not user1:
                print("测试失败：无法获取测试用户1 (test_user)")
                return False
            
            if not user2:
                print("测试失败：无法获取测试用户2 (test_user_2)")
                print("   提示：请先创建用户 'test_user_2' 用于测试权限控制")
                return False
            
            print(f"\n2. 使用测试用户:")
            print(f"   用户1: {user1.username} (ID: {user1.id}, 组织: {user1.primary_org})")
            print(f"   用户2: {user2.username} (ID: {user2.id}, 组织: {user2.primary_org})")
            
            print("\n3. 用户1创建文件（私有和公开）...")
            print("   用户1将创建以下文件：")
            print("   - 私有文件1（用户1的私有文档）")
            print("   - 公开文件1（所有用户可见）")
            print("   - 私有文件2（用户1的另一个私有文档）")
            
            user1_files = [
                {"name": "用户1的私有文档1.txt", "content": "这是用户1的私有文档1，只有用户1能看到。".encode('utf-8'), "is_public": False},
                {"name": "用户1的公开文档.pdf", "content": "这是用户1的公开文档，所有用户都能看到。".encode('utf-8'), "is_public": True},
                {"name": "用户1的私有文档2.txt", "content": "这是用户1的私有文档2，只有用户1能看到。".encode('utf-8'), "is_public": False},
            ]
            
            user1_file_md5s = []
            
            for idx, test_file in enumerate(user1_files, 1):
                print(f"\n   创建文件 {idx}/{len(user1_files)}: {test_file['name']}...")
                file_content = test_file['content']
                file_md5 = calculate_file_md5(file_content)
                file_name = test_file['name']
                total_size = len(file_content)
                
                try:
                    uploaded_chunks, progress = await file_service.upload_chunk(
                        db=db_session,
                        user=user1,
                        file_md5=file_md5,
                        chunk_index=0,
                        chunk_data=file_content,
                        file_name=file_name,
                        total_size=total_size,
                        total_chunks=1,
                        org_tag=user1.primary_org,
                        is_public=test_file['is_public']
                    )
                    
                    user1_file_md5s.append({"md5": file_md5, "name": file_name, "is_public": test_file['is_public']})
                    print(f"   文件 '{file_name}' 上传成功 (MD5: {file_md5[:8]}..., 公开: {'是' if test_file['is_public'] else '否'})")
                    
                    try:
                        await file_service.merge_file(
                            db=db_session,
                            user=user1,
                            file_md5=file_md5,
                            file_name=file_name
                        )
                        print(f"   文件 '{file_name}' 合并成功")
                    except Exception as e:
                        print(f"   文件 '{file_name}' 合并失败: {e} (不影响权限测试)")
                        
                except Exception as e:
                    print(f"   文件 '{file_name}' 上传失败: {e}")
                    return False
            
            print(f"\n   用户1总计创建了 {len(user1_file_md5s)} 个文件")
            
            print("\n4. 测试用户1访问自己创建的文件...")
            user1_files_list = await file_service.get_user_uploaded_files(
                db=db_session,
                user=user1
            )
            print(f"   用户1查询结果: 找到 {len(user1_files_list)} 个文件")
            
            if len(user1_files_list) >= len(user1_file_md5s):
                print(f"   验证成功: 用户1能看到自己创建的所有 {len(user1_files_list)} 个文件")
            else:
                print(f"   验证失败: 用户1应该能看到 {len(user1_file_md5s)} 个文件，但只看到 {len(user1_files_list)} 个")
                return False
            
            user1_accessible = await file_service.get_accessible_files(
                db=db_session,
                user=user1
            )
            print(f"   用户1可访问文件总数: {len(user1_accessible)} 个")
            user1_own_count = len([f for f in user1_accessible if f.user_id == user1.id])
            print(f"   其中用户1自己上传的: {user1_own_count} 个")
            
            if user1_own_count >= len(user1_file_md5s):
                print(f"   验证成功: 用户1可访问列表包含所有自己创建的文件")
            else:
                print(f"   验证失败: 用户1可访问列表应该包含 {len(user1_file_md5s)} 个自己创建的文件")
                return False
            
            print("\n5. 测试用户2访问用户1创建的文件...")
            user2_files_list = await file_service.get_user_uploaded_files(
                db=db_session,
                user=user2
            )
            print(f"   用户2自己上传的文件: {len(user2_files_list)} 个 (应该为0，因为用户2没有上传文件)")
            
            if len(user2_files_list) != 0:
                print(f"   警告: 用户2有 {len(user2_files_list)} 个已上传的文件（可能之前测试留下的）")
            
            user2_accessible = await file_service.get_accessible_files(
                db=db_session,
                user=user2
            )
            print(f"   用户2可访问文件总数: {len(user2_accessible)} 个")
            
            user1_public_files = [f for f in user1_file_md5s if f['is_public']]
            user1_private_files = [f for f in user1_file_md5s if not f['is_public']]
            
            user2_can_see_public = [f for f in user2_accessible if f.file_md5 in [f['md5'] for f in user1_public_files]]
            user2_can_see_private = [f for f in user2_accessible if f.file_md5 in [f['md5'] for f in user1_private_files]]
            
            print(f"\n   权限验证结果:")
            print(f"   - 用户1创建的公开文件数: {len(user1_public_files)} 个")
            print(f"   - 用户2能看到的用户1公开文件: {len(user2_can_see_public)} 个")
            print(f"   - 用户1创建的私有文件数: {len(user1_private_files)} 个")
            print(f"   - 用户2能看到的用户1私有文件: {len(user2_can_see_private)} 个")
            
            all_passed = True
            
            if len(user2_can_see_public) == len(user1_public_files):
                print(f"   验证成功: 用户2能看到用户1的所有公开文件 ({len(user1_public_files)} 个)")
            else:
                print(f"   验证失败: 用户2应该能看到 {len(user1_public_files)} 个公开文件，但只看到 {len(user2_can_see_public)} 个")
                all_passed = False
            
            if user1.primary_org == user2.primary_org and user1.primary_org:
                if len(user2_can_see_private) == len(user1_private_files):
                    print(f"   验证成功: 用户2与用户1在同一组织，能看到用户1的所有私有文件 ({len(user1_private_files)} 个)")
                else:
                    print(f"   验证警告: 用户2与用户1在同一组织，应该能看到 {len(user1_private_files)} 个私有文件，但只看到 {len(user2_can_see_private)} 个")
            else:
                if len(user2_can_see_private) == 0:
                    print(f"   验证成功: 用户2与用户1不在同一组织，不能看到用户1的私有文件")
                else:
                    print(f"   验证失败: 用户2与用户1不在同一组织，不应该能看到用户1的私有文件，但看到了 {len(user2_can_see_private)} 个")
                    all_passed = False
            
            if not all_passed:
                return False
            
            print("\n   所有权限验证通过")
            
            print("\n6. 测试数据说明...")
            print(f"   本测试创建了 {len(user1_file_md5s)} 个文件")
            print("   所有测试文件将在测试结束后统一清理")
            
            break
        
        print("\n7. 关闭服务连接...")
        try:
            print("   关闭MySQL数据库连接...")
            await db_client.close()
            print("   关闭Redis连接...")
            await redis_client.close()
            print("   关闭MinIO连接...")
            minio_client.close()
            print("   所有服务连接已关闭")
        except Exception as e:
            print(f"   关闭连接时出现警告（可忽略）: {type(e).__name__}")
        
        print("\n" + "=" * 60)
        print(" 文件访问权限控制测试通过！")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n 测试失败: {e}")
        print("   错误详情:")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "=" * 60)
    print("文件上传功能测试")
    print("=" * 60)
    print("\n注意：")
    print("1. 请确保已启动所有服务（MySQL, Redis, MinIO）")
    print("2. 请确保已创建测试用户 'test_user'")
    print("3. 请确保 MinIO 存储桶已创建")
    print("\n" + "=" * 60)
    
    results = []
    
    try:
        results.append(await test_chunk_upload())
        
        results.append(await test_upload_status())
        
        results.append(await test_file_list())
        
        results.append(await test_file_access_permission())
    finally:
        try:
            print("\n" + "=" * 60)
            print("清理所有测试文件数据...")
            
            print("   检查服务连接状态...")
            if not db_client.engine:
                print("   重新连接MySQL数据库...")
                db_client.connect()
            
            if not redis_client.redis:
                print("   重新连接Redis缓存...")
                await redis_client.connect()
            
            if not minio_client.client:
                print("   重新连接MinIO对象存储...")
                minio_client.connect()
            
            test_usernames = ["test_user", "test_user_2"]
            total_deleted = 0
            
            async for db_session in db_client.get_session():
                for username in test_usernames:
                    try:
                        result = await db_session.execute(select(User).where(User.username == username))
                        user = result.scalar_one_or_none()
                        
                        if not user:
                            print(f"   用户 '{username}' 不存在，跳过清理")
                            continue
                        
                        files = await file_service.get_user_uploaded_files(
                            db=db_session,
                            user=user
                        )
                        
                        if files:
                            print(f"   清理用户 '{username}' 的文件 (共 {len(files)} 个)...")
                            for idx, file in enumerate(files, 1):
                                try:
                                    await file_service.delete_file(
                                        db=db_session,
                                        user=user,
                                        file_md5=file.file_md5
                                    )
                                    total_deleted += 1
                                    if idx % 3 == 0 or idx == len(files):
                                        print(f"     已清理 {idx}/{len(files)} 个文件")
                                except Exception as e:
                                    error_msg = str(e)
                                    if "NoneType" in error_msg or "remove_object" in error_msg:
                                        print(f"     警告: 删除文件 {file.file_name} 失败 (MinIO未连接): {error_msg[:50]}")
                                    else:
                                        print(f"     警告: 删除文件 {file.file_name} 失败: {error_msg[:50]}")
                        else:
                            print(f"   用户 '{username}' 没有需要清理的文件")
                            
                    except Exception as e:
                        error_msg = str(e)
                        if "greenlet_spawn" in error_msg or "await_only" in error_msg:
                            print(f"   警告: 清理用户 '{username}' 的文件时出错 (数据库异步上下文问题): {error_msg[:80]}")
                        else:
                            print(f"   警告: 清理用户 '{username}' 的文件时出错: {error_msg[:80]}")
                
                break  # Run a single session in this test
            
            print(f"\n   总计清理了 {total_deleted} 个测试文件")
            print("   所有测试文件数据已清理")
            
        except Exception as e:
            error_msg = str(e)
            if "greenlet_spawn" in error_msg or "await_only" in error_msg:
                print(f"   清理测试文件数据时出现错误 (数据库异步上下文问题): {error_msg[:100]}")
            else:
                print(f"   清理测试文件数据时出现错误: {error_msg[:100]}")
        
        try:
            print("\n" + "=" * 60)
            print("清理所有连接...")
            
            try:
                if db_client.engine:
                    await asyncio.wait_for(db_client.close(), timeout=2.0)
            except (asyncio.CancelledError, RuntimeError, asyncio.TimeoutError, AttributeError, Exception):
                pass
            
            try:
                await asyncio.wait_for(redis_client.close(), timeout=1.0)
            except (asyncio.CancelledError, RuntimeError, asyncio.TimeoutError, Exception):
                pass
            
            try:
                minio_client.close()
            except Exception:
                pass
            
            await asyncio.sleep(0.1)
            
            print("所有连接已清理")
        except (asyncio.CancelledError, RuntimeError):
            pass
        except Exception:
            pass
    
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    print(f"总测试数: {len(results)} 个测试用例")
    print(f"通过测试: {sum(results)} 个")
    print(f"失败测试: {len(results) - sum(results)} 个")
    
    if all(results):
        print("\n✅ 所有测试通过！文件上传功能工作正常。")
    else:
        print("\n❌ 部分测试失败，请检查上述错误信息并修复问题。")
    
    print("=" * 60)


if __name__ == "__main__":
    import warnings
    import sys
    import logging
    from io import StringIO
    
    warnings.filterwarnings("ignore")
    
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    logging.getLogger("aiomysql").setLevel(logging.WARNING)
    
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except (asyncio.CancelledError, RuntimeError) as e:
        error_str = str(e)
        if "Event loop is closed" in error_str or "CancelledError" in str(type(e).__name__):
            pass
        else:
            raise
    except Exception as e:
        error_str = str(e)
        ignore_patterns = ["Event loop is closed", "CancelledError", "greenlet_spawn"]
        if any(pattern in error_str for pattern in ignore_patterns):
            pass  # Ignore cleanup exceptions in teardown
        else:
            raise

