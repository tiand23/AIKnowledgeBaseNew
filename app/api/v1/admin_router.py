"""
管理员接口
"""
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List
from app.api.deps import get_db, get_current_user
from app.models.user import User, UserRole
from app.models.organization import OrganizationTag
from app.schemas.admin import (
    CreateOrgTagRequest,
    CreateOrgTagResponse,
    AssignOrgTagsRequest,
    AssignOrgTagsResponse,
    SetPrimaryOrgRequest,
    SetPrimaryOrgResponse,
    UserOrgTagsResponse,
    UserOrgTagsData,
    OrgTagDetail,
    OrgTagTreeResponse,
    OrgTagTreeNode,
    UpdateOrgTagRequest,
    UpdateOrgTagResponse,
    DeleteOrgTagResponse,
)

router = APIRouter()


async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，需要管理员权限"
        )
    return current_user


@router.post("/org-tags", response_model=CreateOrgTagResponse)
async def create_org_tag(
    request_data: CreateOrgTagRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    创建组织标签（仅管理员）
    
    - 验证标签ID是否已存在
    - 如果指定父标签，验证父标签是否存在
    - 创建组织标签记录
    """
    result = await db.execute(
        select(OrganizationTag).where(OrganizationTag.tag_id == request_data.tagId)
    )
    existing_tag = result.scalar_one_or_none()
    
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="标签ID已存在"
        )
    
    if request_data.parentTag:
        parent_result = await db.execute(
            select(OrganizationTag).where(OrganizationTag.tag_id == request_data.parentTag)
        )
        parent_tag = parent_result.scalar_one_or_none()
        
        if not parent_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父标签不存在"
            )
    
    new_tag = OrganizationTag(
        tag_id=request_data.tagId,
        name=request_data.name,
        description=request_data.description,
        parent_tag=request_data.parentTag,
        created_by=admin_user.id,
    )
    
    db.add(new_tag)
    await db.commit()
    await db.refresh(new_tag)
    
    return CreateOrgTagResponse(
        code=200,
        message="Organization tag created successfully",
        data=None
    )


@router.put("/org-tags", response_model=AssignOrgTagsResponse)
async def assign_org_tags(
    request_data: AssignOrgTagsRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    为用户分配组织标签（仅管理员）
    
    - 验证用户是否存在
    - 验证所有组织标签是否存在
    - 更新用户的组织标签
    """
    user_result = await db.execute(
        select(User).where(User.id == request_data.userId)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if request_data.orgTags:
        for tag_id in request_data.orgTags:
            tag_result = await db.execute(
                select(OrganizationTag).where(OrganizationTag.tag_id == tag_id)
            )
            tag = tag_result.scalar_one_or_none()
            
            if not tag:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"组织标签 '{tag_id}' 不存在"
                )
    
    user.org_tags = ",".join(request_data.orgTags) if request_data.orgTags else None
    
    if request_data.orgTags and len(request_data.orgTags) == 1:
        user.primary_org = request_data.orgTags[0]
    elif not request_data.orgTags:
        user.primary_org = None
    
    await db.commit()
    await db.refresh(user)
    
    return AssignOrgTagsResponse(
        code=200,
        message="Organization tags assigned successfully",
        data=None
    )


@router.put("/primary-org", response_model=SetPrimaryOrgResponse)
async def set_primary_org(
    request_data: SetPrimaryOrgRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    设置用户主组织（仅管理员）
    
    - 验证用户是否存在
    - 验证主组织标签是否存在
    - 验证主组织标签是否在用户的组织标签列表中
    - 更新用户的主组织标签
    """
    user_result = await db.execute(
        select(User).where(User.id == request_data.userId)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    tag_result = await db.execute(
        select(OrganizationTag).where(OrganizationTag.tag_id == request_data.primaryOrg)
    )
    tag = tag_result.scalar_one_or_none()
    
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="主组织标签不存在"
        )
    
    user_org_tags = []
    if user.org_tags:
        user_org_tags = [tag.strip() for tag in user.org_tags.split(",") if tag.strip()]
    
    if request_data.primaryOrg not in user_org_tags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="主组织标签必须在用户的组织标签列表中"
        )
    
    user.primary_org = request_data.primaryOrg
    
    await db.commit()
    await db.refresh(user)
    
    return SetPrimaryOrgResponse(
        code=200,
        message="Primary organization set successfully",
        data=None
    )


@router.get("/users/org-tags", response_model=UserOrgTagsResponse)
async def get_user_org_tags(
    userId: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    获取用户组织标签详情（仅管理员）
    
    - 验证用户是否存在
    - 查询用户的所有组织标签详情
    """
    user_result = await db.execute(
        select(User).where(User.id == userId)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    org_tags_list: List[str] = []
    if user.org_tags:
        org_tags_list = [tag.strip() for tag in user.org_tags.split(",") if tag.strip()]
    
    org_tag_details = []
    if org_tags_list:
        tags_result = await db.execute(
            select(OrganizationTag).where(OrganizationTag.tag_id.in_(org_tags_list))
        )
        tags = tags_result.scalars().all()
        
        for tag in tags:
            org_tag_details.append(OrgTagDetail(
                tagId=tag.tag_id,
                name=tag.name,
                description=tag.description
            ))
    
    return UserOrgTagsResponse(
        code=200,
        message="Get user organization tags successful",
        data=UserOrgTagsData(
            orgTags=org_tags_list,
            primaryOrg=user.primary_org,
            orgTagDetails=org_tag_details
        )
    )


@router.get("/org-tags/tree", response_model=OrgTagTreeResponse)
async def get_org_tag_tree(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    获取组织标签树（仅管理员）
    
    - 查询所有组织标签
    - 构建树形结构
    """
    result = await db.execute(select(OrganizationTag))
    all_tags = result.scalars().all()
    
    tag_dict = {tag.tag_id: tag for tag in all_tags}
    
    def build_tree_node(tag: OrganizationTag) -> OrgTagTreeNode:
        children_tags = [t for t in all_tags if t.parent_tag == tag.tag_id]
        children_nodes = [build_tree_node(child) for child in children_tags]
        
        return OrgTagTreeNode(
            tagId=tag.tag_id,
            name=tag.name,
            description=tag.description,
            children=children_nodes
        )
    
    root_tags = [tag for tag in all_tags if tag.parent_tag is None]
    tree = [build_tree_node(root) for root in root_tags]
    
    return OrgTagTreeResponse(
        code=200,
        message="Get organization tag tree successful",
        data=tree
    )


@router.put("/org-tags/{tag_id}", response_model=UpdateOrgTagResponse)
async def update_org_tag(
    tag_id: str = Path(..., description="标签ID"),
    request_data: UpdateOrgTagRequest = ...,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    更新组织标签（仅管理员）
    
    - 验证标签是否存在
    - 如果指定父标签，验证父标签是否存在且不能是自己
    - 更新标签信息
    """
    tag_result = await db.execute(
        select(OrganizationTag).where(OrganizationTag.tag_id == tag_id)
    )
    tag = tag_result.scalar_one_or_none()
    
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织标签不存在"
        )
    
    if request_data.parentTag:
        if request_data.parentTag == tag_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能将自己设为父标签"
            )
        
        parent_result = await db.execute(
            select(OrganizationTag).where(OrganizationTag.tag_id == request_data.parentTag)
        )
        parent_tag = parent_result.scalar_one_or_none()
        
        if not parent_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父标签不存在"
            )
        
        current_parent = parent_tag
        while current_parent:
            if current_parent.tag_id == tag_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="不能设置父标签，会导致循环引用"
                )
            if current_parent.parent_tag:
                parent_check = await db.execute(
                    select(OrganizationTag).where(OrganizationTag.tag_id == current_parent.parent_tag)
                )
                current_parent = parent_check.scalar_one_or_none()
            else:
                break
    
    if request_data.name is not None:
        tag.name = request_data.name
    if request_data.description is not None:
        tag.description = request_data.description
    if request_data.parentTag is not None:
        tag.parent_tag = request_data.parentTag
    
    await db.commit()
    await db.refresh(tag)
    
    return UpdateOrgTagResponse(
        code=200,
        message="Organization tag updated successfully",
        data=None
    )


@router.delete("/org-tags/{tag_id}", response_model=DeleteOrgTagResponse)
async def delete_org_tag(
    tag_id: str = Path(..., description="标签ID"),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    删除组织标签（仅管理员）
    
    - 验证标签是否存在
    - 检查标签是否被用户或文档使用
    - 如果被使用，返回 409 错误
    - 如果未被使用，删除标签
    """
    tag_result = await db.execute(
        select(OrganizationTag).where(OrganizationTag.tag_id == tag_id)
    )
    tag = tag_result.scalar_one_or_none()
    
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="组织标签不存在"
        )
    
    user_result = await db.execute(
        select(User).where(
            or_(
                User.org_tags.like(f"%{tag_id}%"),
                User.primary_org == tag_id
            )
        )
    )
    users_using_tag = user_result.scalars().all()
    
    children_result = await db.execute(
        select(OrganizationTag).where(OrganizationTag.parent_tag == tag_id)
    )
    children = children_result.scalars().all()
    
    if users_using_tag or children:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete tag as it is associated with users or has children tags"
        )
    
    await db.delete(tag)
    await db.commit()
    
    return DeleteOrgTagResponse(
        code=200,
        message="Organization tag deleted successfully",
        data=None
    )

