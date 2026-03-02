"""
文件相关模型
"""
from sqlalchemy import Column, String, BigInteger, Integer, Boolean, DateTime, ForeignKey, SmallInteger, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base, BIGINT_TYPE

FILE_STATUS_UPLOADING = 0
FILE_STATUS_MERGED = 1
FILE_STATUS_PROCESSING = 2
FILE_STATUS_DONE = 3
FILE_STATUS_FAILED = 4


class FileUpload(Base):
    
    __tablename__ = "file_upload"
    
    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment='主键')
    file_md5 = Column(String(32), nullable=False, index=True, unique=True, comment='文件MD5指纹')
    file_name = Column(String(255), nullable=False, comment='文件名称')
    total_size = Column(BigInteger, nullable=False, comment='文件大小（字节）')
    status = Column(
        SmallInteger,
        nullable=False,
        default=FILE_STATUS_UPLOADING,
        comment='文件状态：0=上传中，1=已合并待处理，2=处理中，3=处理完成，4=处理失败'
    )
    user_id = Column(BIGINT_TYPE, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    org_tag = Column(String(50), ForeignKey('organization_tags.tag_id', ondelete='SET NULL'), comment='组织标签')
    kb_profile = Column(String(32), nullable=False, default='general', comment='知识库场景配置ID')
    is_public = Column(Boolean, nullable=False, default=False, comment='是否公开')
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment='创建时间')
    merged_at = Column(DateTime, nullable=True, onupdate=func.now(), comment='合并时间')
    
    user = relationship("User", backref="uploaded_files")
    organization = relationship("OrganizationTag", backref="files")
    chunks = relationship("ChunkInfo", back_populates="file", cascade="all, delete-orphan")
    vectors = relationship("DocumentVector", back_populates="file", cascade="all, delete-orphan")
    table_rows = relationship("TableRow", back_populates="file", cascade="all, delete-orphan")
    image_blocks = relationship("ImageBlock", back_populates="file", cascade="all, delete-orphan")
    relation_nodes = relationship("RelationNode", back_populates="file", cascade="all, delete-orphan")
    relation_edges = relationship("RelationEdge", back_populates="file", cascade="all, delete-orphan")
    experience_items = relationship("ExperienceItem", back_populates="file", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<FileUpload(id={self.id}, file_name={self.file_name}, status={self.status})>"

    __table_args__ = (
        # UNIQUE KEY uk_md5_user (file_md5, user_id)
        UniqueConstraint('file_md5', 'user_id', name='uk_md5_user'),
        # INDEX idx_user (user_id)
        Index('idx_user', 'user_id'),
        # INDEX idx_org_tag (org_tag)
        Index('idx_org_tag', 'org_tag'),
        Index('idx_kb_profile', 'kb_profile'),
    )


class ChunkInfo(Base):
    
    __tablename__ = "chunk_info"
    
    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment='主键')
    file_md5 = Column(String(32), ForeignKey('file_upload.file_md5', ondelete='CASCADE', onupdate='CASCADE'), nullable=False, comment='文件MD5（外键）')
    chunk_index = Column(Integer, nullable=False, comment='分片序号（0-based）')
    chunk_md5 = Column(String(32), nullable=False, comment='分片MD5校验')
    storage_path = Column(String(255), nullable=False, comment='分片存储路径（如 MinIO URL）')
    
    file = relationship("FileUpload", back_populates="chunks")
    
    def __repr__(self):
        return f"<ChunkInfo(id={self.id}, file_md5={self.file_md5}, chunk_index={self.chunk_index})>"

    __table_args__ = (
        UniqueConstraint('file_md5', 'chunk_index', name='uk_chunk_file_index'),
        Index('idx_file_chunk', 'file_md5', 'chunk_index'),
    )


class DocumentVector(Base):
    
    __tablename__ = "document_vectors"
    
    vector_id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment='主键，自增ID')
    file_md5 = Column(String(32), ForeignKey('file_upload.file_md5', ondelete='CASCADE', onupdate='CASCADE'), nullable=False, comment='文件指纹（关联file_upload表）')
    chunk_id = Column(Integer, nullable=False, comment='文本分块序号')
    text_content = Column(Text, comment='原始文本内容')
    model_version = Column(String(32), default='all-MiniLM-L6-v2', comment='生成向量所使用的模型版本')
    
    file = relationship("FileUpload", back_populates="vectors")
    
    def __repr__(self):
        return f"<DocumentVector(vector_id={self.vector_id}, file_md5={self.file_md5}, chunk_id={self.chunk_id})>"

    __table_args__ = (
        Index('idx_file_chunk_vectors', 'file_md5', 'chunk_id'),
    )


class ChunkSource(Base):

    __tablename__ = "chunk_sources"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    file_md5 = Column(
        String(32),
        ForeignKey("file_upload.file_md5", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="文件MD5",
    )
    chunk_id = Column(Integer, nullable=False, comment="检索分块ID（与 ES chunk_id 对齐）")
    source_order = Column(Integer, nullable=False, default=0, comment="该 chunk 内证据顺序")
    block_index = Column(Integer, nullable=True, comment="来源 block 序号")
    source_type = Column(String(32), nullable=True, comment="来源类型：table_row/diagram_edge/xlsx_image/...")
    source_parser = Column(String(32), nullable=True, comment="来源解析器")
    sheet = Column(String(128), nullable=True, comment="sheet 名称（Excel）")
    page = Column(Integer, nullable=True, comment="页码（PDF等）")
    section = Column(String(255), nullable=True, comment="章节/段落")
    image_path = Column(String(255), nullable=True, comment="关联图片对象路径")
    text_preview = Column(Text, nullable=True, comment="证据文本摘要")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    file = relationship("FileUpload")

    __table_args__ = (
        Index("idx_chunk_sources_file_chunk", "file_md5", "chunk_id"),
        Index("idx_chunk_sources_sheet", "sheet"),
        Index("idx_chunk_sources_page", "page"),
        Index("idx_chunk_sources_image", "image_path"),
        UniqueConstraint("file_md5", "chunk_id", "source_order", name="uk_chunk_sources_fcs"),
    )


class TableRow(Base):

    __tablename__ = "table_rows"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    file_md5 = Column(
        String(32),
        ForeignKey("file_upload.file_md5", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="文件MD5",
    )
    sheet = Column(String(128), nullable=True, comment="sheet 名称")
    table_name = Column(String(128), nullable=True, comment="表名称（如 table_1）")
    row_no = Column(Integer, nullable=True, comment="行号（1-based）")
    row_json = Column(Text, nullable=False, comment="行数据 JSON 字符串")
    raw_text = Column(Text, nullable=True, comment="行文本（检索辅助）")
    source_parser = Column(String(32), nullable=False, default="table", comment="来源解析器")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    file = relationship("FileUpload", back_populates="table_rows")

    __table_args__ = (
        Index("idx_table_rows_file", "file_md5"),
        Index("idx_table_rows_sheet", "sheet"),
        Index("idx_table_rows_table", "table_name"),
        Index("idx_table_rows_row_no", "row_no"),
    )


class ImageBlock(Base):

    __tablename__ = "image_blocks"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    file_md5 = Column(
        String(32),
        ForeignKey("file_upload.file_md5", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="文件MD5",
    )
    sheet = Column(String(128), nullable=True, comment="sheet名称")
    page = Column(Integer, nullable=True, comment="页码（非Excel可用）")
    anchor_row = Column(Integer, nullable=True, comment="锚点行（1-based）")
    anchor_col = Column(Integer, nullable=True, comment="锚点列（1-based）")
    storage_path = Column(String(255), nullable=False, comment="MinIO对象路径")
    image_md5 = Column(String(32), nullable=True, comment="图片MD5")
    image_width = Column(Integer, nullable=True, comment="图片宽")
    image_height = Column(Integer, nullable=True, comment="图片高")
    content_type = Column(String(64), nullable=True, comment="图片类型")
    description = Column(Text, nullable=True, comment="图片描述（来自邻近单元格）")
    source_parser = Column(String(32), nullable=False, default="xlsx_image", comment="解析器来源")
    match_mode = Column(String(32), nullable=True, comment="快照page->sheet绑定模式")
    match_confidence = Column(Integer, nullable=True, comment="快照绑定置信度(0-100)")
    match_reason = Column(Text, nullable=True, comment="快照绑定说明/原因")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    file = relationship("FileUpload", back_populates="image_blocks")

    __table_args__ = (
        Index("idx_image_blocks_file", "file_md5"),
        Index("idx_image_blocks_sheet", "sheet"),
        Index("idx_image_blocks_sheet_page", "sheet", "page"),
        Index("idx_image_blocks_anchor", "anchor_row", "anchor_col"),
    )


class RelationNode(Base):

    __tablename__ = "relation_nodes"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    file_md5 = Column(
        String(32),
        ForeignKey("file_upload.file_md5", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="文件MD5"
    )
    node_key = Column(String(128), nullable=False, comment="标准化节点键（去空白小写）")
    node_name = Column(String(255), nullable=False, comment="节点原始名称")
    node_type = Column(String(50), nullable=True, comment="节点类型（可选）")
    page = Column(Integer, nullable=True, comment="页码")
    evidence_text = Column(Text, nullable=True, comment="证据文本")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    file = relationship("FileUpload", back_populates="relation_nodes")
    outgoing_edges = relationship(
        "RelationEdge",
        foreign_keys="RelationEdge.src_node_id",
        back_populates="src_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "RelationEdge",
        foreign_keys="RelationEdge.dst_node_id",
        back_populates="dst_node",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_relation_nodes_file", "file_md5"),
        Index("idx_relation_nodes_key", "node_key"),
        Index("idx_relation_nodes_name", "node_name"),
        UniqueConstraint("file_md5", "node_key", name="uk_relation_nodes_file_key"),
    )


class RelationEdge(Base):

    __tablename__ = "relation_edges"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    file_md5 = Column(
        String(32),
        ForeignKey("file_upload.file_md5", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="文件MD5"
    )
    src_node_id = Column(
        BIGINT_TYPE,
        ForeignKey("relation_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="源节点ID"
    )
    dst_node_id = Column(
        BIGINT_TYPE,
        ForeignKey("relation_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="目标节点ID"
    )
    relation_type = Column(String(64), nullable=False, comment="关系类型（输入/输出/依赖/调用...）")
    relation_text = Column(String(255), nullable=True, comment="关系原文片段")
    page = Column(Integer, nullable=True, comment="页码")
    evidence_text = Column(Text, nullable=True, comment="证据文本")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    file = relationship("FileUpload", back_populates="relation_edges")
    src_node = relationship("RelationNode", foreign_keys=[src_node_id], back_populates="outgoing_edges")
    dst_node = relationship("RelationNode", foreign_keys=[dst_node_id], back_populates="incoming_edges")

    __table_args__ = (
        Index("idx_relation_edges_file", "file_md5"),
        Index("idx_relation_edges_src", "src_node_id"),
        Index("idx_relation_edges_dst", "dst_node_id"),
        Index("idx_relation_edges_type", "relation_type"),
    )


class ExperienceItem(Base):

    __tablename__ = "experience_items"

    id = Column(BIGINT_TYPE, primary_key=True, autoincrement=True, comment="主键")
    file_md5 = Column(
        String(32),
        ForeignKey("file_upload.file_md5", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="文件MD5",
    )
    person_name = Column(String(128), nullable=True, comment="姓名（可为空）")
    project_name = Column(String(255), nullable=False, comment="项目/系统名称")
    role_summary = Column(String(255), nullable=True, comment="角色/职责摘要")
    start_ym = Column(Integer, nullable=True, comment="开始年月（YYYYMM）")
    end_ym = Column(Integer, nullable=True, comment="结束年月（YYYYMM），进行中用当前年月")
    period_text = Column(String(64), nullable=True, comment="原始期间文本")
    source_chunk_id = Column(Integer, nullable=True, comment="来源chunk_id")
    evidence_text = Column(Text, nullable=True, comment="证据片段")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="创建时间")

    file = relationship("FileUpload", back_populates="experience_items")

    __table_args__ = (
        Index("idx_exp_file", "file_md5"),
        Index("idx_exp_person", "person_name"),
        Index("idx_exp_end_ym", "end_ym"),
        Index("idx_exp_project", "project_name"),
    )
