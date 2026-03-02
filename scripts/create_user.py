"""
直接在数据库中创建用户
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.clients.db_client import db_client
from app.models.user import User, UserRole
from app.models.organization import OrganizationTag
from app.utils.security import hash_password
from app.core.config import settings


async def create_user(
    username: str,
    email: str,
    password: str,
    role: UserRole = UserRole.USER,
    org_tags: str = None,
    primary_org: str = None,
    create_private_org: bool = True
):
    """
    创建用户
    
    Args:
        username: 用户名
        email: 邮箱
        password: 密码（明文，会自动加密）
        role: 用户角色（USER 或 ADMIN）
        org_tags: 组织标签（逗号分隔）
        primary_org: 主组织标签
        create_private_org: 是否创建私人组织标签
    """
    print("=" * 60)
    print("创建用户")
    print("=" * 60)
    
    try:
        print("\n1. 连接数据库...")
        db_client.connect()
        print("数据库连接成功")
        
        async for session in db_client.get_session():
            print(f"\n2. 检查用户 '{username}' 是否已存在...")
            result = await session.execute(select(User).where(User.username == username))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"用户名 '{username}' 已存在！")
                print(f"   用户ID: {existing_user.id}")
                print(f"   邮箱: {existing_user.email}")
                return False
            
            result = await session.execute(select(User).where(User.email == email))
            existing_email = result.scalar_one_or_none()
            
            if existing_email:
                print(f"邮箱 '{email}' 已被使用！")
                return False
            
            print("\n3. 加密密码...")
            try:
                import warnings
                import sys
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    original_stderr = sys.stderr
                    try:
                        from io import StringIO
                        sys.stderr = StringIO()
                        hashed_password = hash_password(password)
                        sys.stderr = original_stderr
                    except Exception:
                        sys.stderr = original_stderr
                        raise
                print("密码加密完成")
            except Exception as e:
                print(f"密码加密失败: {e}")
                return False
            
            print("\n4. 创建用户...")
            new_user = User(
                username=username,
                email=email,
                password=hashed_password,
                role=role,
                org_tags=org_tags,
                primary_org=primary_org
            )
            
            session.add(new_user)
            await session.flush()  # Populate user ID
            
            print(f"用户创建成功 (ID: {new_user.id})")
            
            if create_private_org:
                print("\n5. 创建私人组织标签...")
                private_tag_id = f"PRIVATE_{username}"
                
                org_result = await session.execute(
                    select(OrganizationTag).where(OrganizationTag.tag_id == private_tag_id)
                )
                existing_tag = org_result.scalar_one_or_none()
                
                if existing_tag:
                    print(f"组织标签 '{private_tag_id}' 已存在，跳过创建")
                    private_tag = existing_tag
                else:
                    private_tag = OrganizationTag(
                        tag_id=private_tag_id,
                        name=f"我的组织-{username}",
                        description=f"用户 {username} 的私人组织",
                        parent_tag=None,
                        created_by=new_user.id
                    )
                    session.add(private_tag)
                    print(f"组织标签创建成功: {private_tag_id}")
                
                if not new_user.org_tags:
                    new_user.org_tags = private_tag_id
                else:
                    org_list = [tag.strip() for tag in new_user.org_tags.split(",") if tag.strip()]
                    if private_tag_id not in org_list:
                        org_list.append(private_tag_id)
                        new_user.org_tags = ",".join(org_list)
                
                if not new_user.primary_org:
                    new_user.primary_org = private_tag_id
            
            await session.commit()
            await session.refresh(new_user)
            
            print("\n" + "=" * 60)
            print("用户创建完成！")
            print("=" * 60)
            print(f"用户ID: {new_user.id}")
            print(f"用户名: {new_user.username}")
            print(f"邮箱: {new_user.email}")
            print(f"角色: {new_user.role.value}")
            print(f"组织标签: {new_user.org_tags}")
            print(f"主组织: {new_user.primary_org}")
            print("=" * 60)
            
            return True
            
    except Exception as e:
        print(f"\n创建用户失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await db_client.close()


async def create_test_user():
    return await create_user(
        username="test_upload_user",
        email="test_upload@example.com",
        password="test123456",
        role=UserRole.USER,
        create_private_org=True
    )


async def create_admin_user():
    return await create_user(
        username="admin",
        email="admin@example.com",
        password="admin123456",
        role=UserRole.ADMIN,
        create_private_org=True
    )


async def main():
    
    # ==========================================
    # ==========================================
    username = "test_user_2"      # Username
    email = "test_user_2@example.com"  # Email
    password = "test"            # Password (plaintext input; hashed before storage)
    role = UserRole.USER               # User role: UserRole.USER or UserRole.ADMIN
    org_tags = None                    # Organization tags (comma-separated, e.g. "DEPT_A,DEPT_B")
    primary_org = None                 # Primary organization tag (e.g. "DEPT_A")
    create_private_org = True          # Whether to create a private organization tag
    
    # ==========================================
    # ==========================================
    await create_user(
        username=username,
        email=email,
        password=password,
        role=role,
        org_tags=org_tags,
        primary_org=primary_org,
        create_private_org=create_private_org
    )


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("用户创建脚本")
    print("=" * 60)
    print("\n注意：")
    print("1. 请确保数据库已启动")
    print("2. 请确保数据库表已创建")
    print("3. 请确保 .env 文件配置正确")
    print("\n" + "=" * 60)
    
    asyncio.run(main())

