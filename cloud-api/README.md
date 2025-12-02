# 云盘示例（cloud-api + frontends/cloud）

> 本 README 只针对「云盘站点」这个子模块，主要用来演示：  
> - 如何在受保护资源端（云盘）接入统一认证中心（auth-server）  
> - OAuth2.0 授权码模式 + 会话管理  
> - 基于登录用户的文件列表、文件上传 / 下载  
> - 文件分享链接 + 可选密码的“加密分享”

---

## 1. 模块结构

云盘相关代码主要分两部分：

```text
cloud-api/              # 云盘后端（Flask）
  app.py                # 主应用，提供 OAuth2 回调 + 文件/分享等 API
  uploads/              # 真实上传文件的存储目录（首次运行会自动创建）

frontends/cloud/        # 云盘前端（纯静态页面）
  cloud.html            # Vue 单页，演示登录、文件列表、上传、分享
````

> 顶层还有 auth-server、academic-api 等模块，用于完整的 SSO 演示，本 README 不再重复。

---

## 2. 功能说明

### 2.1 SSO / OAuth2.0 登录

* 云盘本身不做登录页面，而是把用户**302 跳转**到统一认证中心 `auth-server`：

  * `GET /session/login` → 302 到认证中心的登录页（`AUTH_PORTAL`）
  * 登录 + 授权成功后，认证中心回调到 `cloud-api` 的 `/session/callback`
* `cloud-api` 在回调中：

  1. 使用授权码 `code` 调 `auth-server` 的 `/auth/token` 换取 `access_token` / `refresh_token`
  2. 在内存中生成一个会话 `cloud_session`
  3. 通过 `Set-Cookie` 下发到浏览器（`httponly + secure + SameSite=None`）
  4. 再 302 回前端页面 `FRONT_URL`（默认是 `https://cloud.localhost:4176/cloud.html`）

前端 `cloud.html` 通过：

* `GET /session/status` 判断当前是否已登录；
* 所有需要登录的操作（列出文件、上传、分享）都带上 `credentials: "include"`，让浏览器自动携带 `cloud_session`。

### 2.2 文件列表

后端接口：

* `GET /files`

行为：

1. 先通过 `_validate_token()` 利用 `cloud_session` 去 `auth-server` 验证 `access_token` 是否有效（必要时自动刷新 `refresh_token`）。
2. 从验证结果中拿到当前用户名 `username`。
3. 在内存列表 `FILES` 中找出 `owner == username` 的所有文件，返回给前端。

返回示例：

```json
{
  "user": "alice",
  "files": [
    {
      "id": "bin-1719900000-abc123",
      "name": "report.pdf",
      "size": "120KB",
      "uploaded_at": "2025-12-01",
      "owner": "alice",
      "encrypted": true,
      "share_token": "4f8b5a8f...",
      "share_password": "123456",
      "share_expires_at": "2025-12-02T10:00:00Z",
      "is_binary": true
    }
  ]
}
```
```

> 注意：内部会有 `storage_path` 字段存储真实文件路径，但不会返回给前端。

### 2.3 文件上传

云盘示例支持两种上传方式：

#### 2.3.1 模拟上传（只写元数据）

* 接口：`POST /files`
* 请求体（JSON）：

```json
{
  "name": "report-123.pdf",
  "size": "4KB"
}
```

* 行为：不保存真实文件，只在 `FILES` 中追加一条记录，作为 demo 用数据。

#### 2.3.2 真实文件上传

* 接口：`POST /files/upload`
* 请求体：`multipart/form-data`，字段名为 `file`
* 行为：

  1. 校验当前用户；
  2. 把上传的文件保存到 `UPLOAD_DIR`（默认 `cloud-api/uploads`）；
  3. 在 `FILES` 中追加一条记录，字段包括：

     * `is_binary = True`
     * `storage_path` = 文件保存的绝对路径（只在后端使用）

返回结果会同时返回当前用户的全部文件列表，方便前端刷新 UI。

### 2.4 文件下载

* 接口：`GET /files/download/<file_id>`

限制：

* 需要登录；
* 仅允许下载：

  * `owner == 当前用户` 且
  * `is_binary == True` 的文件（即真实上传的文件）。

后端通过 `send_file()` 以附件形式返回文件内容。

### 2.5 文件分享 / 加密分享

#### 2.5.1 创建或更新分享

* 接口：`POST /files/share`
* 请求体（JSON）：

```json
{
  "file_id": "bin-1719900000-abc123",
  "expire_hours": 24,
  "password": "123456"  // 可选，不填则为公开分享
}
```

行为：

1. 校验登录用户，只能分享自己的文件；
2. 生成一个随机 `share_token`；
3. 按 `expire_hours` 计算过期时间；
4. 在对应文件上写入：

   * `share_token`
   * `share_password`（明文，演示用）
   * `share_expires_at`
   * `encrypted = bool(password)` 用来在前端标记“加密分享”
5. 在全局 `SHARES` 中记录一条分享元数据：

   * `token` / `file_id` / `owner` / `password` / `expires_at`

返回示例：

```json
{
  "message": "share created",
  "share_token": "4f8b5a8f...",
  "share_url": "https://cloud.localhost:5002/share/4f8b5a8f...",
  "expires_at": "2025-12-02T10:00:00Z",
  "need_password": true
}
```

#### 2.5.2 访问分享链接

* 接口：`GET /share/<token>?password=xxx`
* 特点：

  * **不需要登录**（模拟“别人拿了分享链接来访问”）
  * 如果分享设置了密码，需要通过 `?password=` 提交正确密码

行为：

1. 查找 `SHARES[token]`，判断是否存在；
2. 判断是否已经过期；
3. 如设置了 `password`，则校验来访者的密码；
4. 返回文件的元信息（不包含 `storage_path`），不做真实下载。

---

## 3. 前端页面 cloud.html

前端位于 `frontends/cloud/cloud.html`，是一个用 CDN 引入 Vue 3 的简单单页应用，主要演示：

* 调 `/session/login` 跳转到统一认证中心；
* 调 `/session/status` 判断登录状态；
* 调 `/files` 拉取当前用户的文件列表；
* 调 `/files`（POST）做模拟“元数据上传”；
* 调 `/files/upload` 上传真实文件；
* 调 `/files/download/<id>` 下载真实文件；
* 调 `/files/share` 创建分享链接；
* 直接展示分享链接 `share_url` 和密码 `share_password`。

UI 上有三个主要区块：

1. **登录卡片**

   * 显示登录状态、当前用户名
   * 提供「前往统一认证」「退出」按钮

2. **文件操作区**

   * 列出文件
   * 模拟上传元数据
   * 真实文件选择 + 上传

3. **文件列表**

   * 每个文件展示：

     * 文件名 / 大小 / 上传时间
     * 是否真实文件（`[真实文件]` 标签）
     * 是否加密分享（`[加密分享]` 标签）
     * 分享链接 + 有效期 + 密码
   * 操作按钮：

     * 设置 / 更新分享
     * （若为真实文件）下载

---

## 4. 运行说明

### 4.1 启动 cloud-api

在 `cloud-api/` 目录下：

```bash
cd cloud-api

# pip install -r ../requirements.txt

python app.py
```

默认会：

* 启动在 `https://cloud.localhost:5002`
* 使用 `certs/cloud-api.crt` 和 `certs/cloud-api.key` 作为 TLS 证书（由顶层项目统一生成）

### 4.2 启动云盘前端

在 `frontends/cloud/` 目录下：

```bash
cd frontends/cloud

python ../https_server.py \
  --ssl-cert ../../certs/cloud-api.crt \
  --ssl-key  ../../certs/cloud-api.key \
  --port 4176
```

然后在浏览器中访问：

```text
https://cloud.localhost:4176/cloud.html
```

**典型操作流程：**

1. 打开云盘前端页面；
2. 点击「前往统一认证（302）」跳转到统一认证中心登录并授权；
3. 回到云盘页面后，点击「列出文件」查看当前用户文件列表；
4. 测试：

   * 模拟上传元数据；
   * 选择一个本地文件并上传真实文件；
   * 对某个文件设置分享链接和访问密码；
   * 使用浏览器访问返回的分享链接，体验有/无密码的访问差异；
   * 对真实文件点击「下载」查看是否正常保存。

---

## 5. 配置项

`cloud-api/app.py` 中支持一些环境变量：

* `AUTH_SERVER`
  默认：`https://auth.localhost:5000`
  说明：统一认证中心 `auth-server` 的访问地址。

* `AUTH_PORTAL`
  默认：`https://auth.localhost:4173/auth.html`
  说明：认证中心的登录/授权入口页面，用于拼出 `login_url`。

* `FRONT_URL`
  默认：`https://cloud.localhost:4176/cloud.html`
  说明：登录完成后，`/session/callback` 302 回前端的地址。

* `CALLBACK_URL`
  默认：`https://cloud.localhost:5002/session/callback`
  说明：在向 `auth-server` 请求授权码时的 `redirect_uri`。

* `CA_CERT_PATH`
  默认：`certs/ca.crt`
  说明：用于校验 `auth-server` 证书的 CA 文件；如果不存在则关闭校验（仅演示用）。

* `UPLOAD_DIR`
  默认：`uploads`
  说明：真实上传文件的存储目录，相对于 `cloud-api/`。

---

## 6. 注意事项 / 限制（仅演示用）

* 所有会话数据（`SESSIONS`）、文件元数据（`FILES`）、分享记录（`SHARES`）都保存在内存中，**进程重启后会丢失**；
* 分享密码在示例中是**明文存储**，仅用于教学演示，不适合真实生产环境；
* `FILES` 中的初始示例文件仅用于演示，并没有真实的二进制内容；
* 分享接口 `/share/<token>` 仅返回元信息，没有实现真实“公开下载文件”的逻辑



