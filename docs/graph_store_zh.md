# Graph Store Design (Chinese)

## 目标

本项目作为通用知识库基盘，Graph 不再只被视为“关系表展示”，而是被定义为正式能力：

1. 页面迁移关系
2. 流程路径关系
3. 模块依赖关系
4. VLM 抽取后的结构关系

当前阶段我们采用：

- PostgreSQL: 业务元数据、ACL、作业状态、证据映射
- PostgreSQL + Apache AGE: graph 主体
- Elasticsearch: text / visual retrieval
- MinIO: 原始文件、页面图、VLM 原始 payload

## Phase 3 目标

这一阶段先做 AGE 的基础骨架，不直接替换现有 `relation_nodes / relation_edges` 查询链路。

当前策略：

1. 现有运行时检索仍使用 `relation_nodes / relation_edges`
2. 新增 Graph backend 配置与 AGE 启动检查
3. 为后续将 Graph 正式写入 AGE 做接口准备

## Graph Backend 配置

新增配置项：

- `GRAPH_BACKEND`
  - `postgres_relational`: 当前默认，继续使用关系表
  - `postgres_age`: 目标模式，使用 PostgreSQL + Apache AGE

- `POSTGRES_AGE_ENABLED`
  - 是否启用 AGE 启动检查

- `POSTGRES_AGE_GRAPH_NAME`
  - 默认 `knowledge_graph`

## Graph Schema（目标）

### Node Labels

- `Page`
- `Component`
- `FlowNode`
- `Task`
- `Entity`

### Edge Labels

- `NAVIGATES_TO`
- `CONTAINS`
- `TRIGGERS`
- `DEPENDS_ON`
- `FLOWS_TO`
- `BELONGS_TO`

## VLM / Graph 分工

VLM 结构结果不会直接整体写入 graph。

建议分层：

1. `raw payload`
   - MinIO + PostgreSQL 元数据

2. `structured facts`
   - PostgreSQL

3. `graph-worthy facts`
   - 仅明确关系（node / edge / path）进入 AGE

4. `text projection`
   - 进入 `semantic_blocks` / `text_index`

## 当前实现边界

`app/services/graph_store_service.py`

当前已经提供：

1. Graph backend 配置抽象
2. AGE schema 常量
3. 启动时的 AGE bootstrap 检查
4. relation index 构建时的 graph dual-write 接口

当前**还没有**做：

1. 基于 Cypher 的查询替换现有 relation search
2. graph 结果返回给问答主链路

## 当前写入策略

当前已实现：

1. `relation_nodes / relation_edges` 继续作为现有检索主数据
2. `RelationSearchService.build_relation_index()` 在构建完成后，会调用 `graph_store_service.sync_relation_facts(...)`
3. 当 `GRAPH_BACKEND=postgres_age` 且 `POSTGRES_AGE_ENABLED=true` 时：
   - 会尝试将 node / edge 同步写入 AGE
4. 当 AGE 未启用时：
   - 该步骤会返回 `skipped`
   - 不影响现有功能

也就是说，当前是：

- **写入双通道**
- **查询仍走旧链路**
- **AGE 作为渐进式目标后端**

## 后续步骤

1. 为 graph write path 设计统一输入格式
2. 将高质量 VLM / diagram facts 同步写入 AGE
3. 新增 graph retrieval service（AGE 优先，关系表 fallback）
4. 接入问答三路融合：
   - text retrieval
   - visual retrieval
   - graph retrieval
