# Frontend (Vue 3 + Vite + TS)

## Start

```bash
cd frontend
npm install
npm run dev
```

默认访问: http://localhost:5173

## Env

可选环境变量（Vite）：

- `VITE_API_BASE_URL`：REST 基地址（默认 `http://localhost:8000`）
- `VITE_WS_BASE_URL`：WebSocket 基地址（默认 `ws://localhost:8000`）

示例 `.env.development`：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

## Pages

- `/login`：用户名密码登录
- `/upload`：文件分片上传 / 查询状态 / 合并
- `/chat`：WebSocket 问答

## Notes

- 上传依赖后端登录态（Bearer Token）。
- 分片上传会计算文件 MD5（spark-md5）。
