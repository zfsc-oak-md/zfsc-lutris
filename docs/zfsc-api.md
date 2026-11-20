# ZFSC API v1 契约

`lutris/services/zfsc.py` 只依赖下面这套只读接口。实现放在 zfsc 仓库，
Lutris 侧不关心数据库结构。

## 认证

所有请求都带：

```http
Authorization: Bearer zfsc_...
Accept: application/json
```

Token 由 zfsc 签发，只存哈希；权限固定为 viewer（可读作品、可下载文件，不能进后台）。
建议格式 `zfsc_` + 32 字节随机数的 base64url，只显示一次。

Token 失效时返回 `401`，不要重定向到登录页。

## GET /api/v1/me

用于 `is_connected()` 和首次连接校验。

```json
{
  "id": 12,
  "login": "alice",
  "role": "viewer"
}
```

## GET /api/v1/works

查询参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `page` | 1 | 从 1 开始 |
| `per_page` | 100 | 上限 200 |
| `with_files` | 0 | `1` 时只返回至少有一个文件的作品 |

响应：

```json
{
  "page": 1,
  "per_page": 100,
  "total": 137,
  "next_page": 2,
  "works": [
    {
      "dlsite_id": "RJ01234567",
      "title": "作品名",
      "circle": "サークル名",
      "work_type": "ADV",
      "tags": ["标签1", "标签2"],
      "description": "简介",
      "cover_url": "https://img.dlsite.jp/...",
      "product_url": "https://www.dlsite.com/maniax/work/=/product_id/RJ01234567.html",
      "release_date": "2024-05-01",
      "rating": "4.6",
      "latest_file": {
        "id": 42,
        "name": "RJ01234567.zip",
        "size": 123456789,
        "sha256": "……",
        "version": "2024-05-01",
        "source": "dlsite"
      }
    }
  ]
}
```

要求：

- `next_page` 在最后一页为 `null`。
- `latest_file` 在没有任何文件时为 `null`。
- `latest_file` 的选择优先级：官方（`source = "dlsite"`）优先于非官方
  （`source = "unofficial"`）；同一来源内按版本日期、`releases.id` 倒序；
  必须取**有文件**的那条，不能只看最新 release。
- `release_date` 归一化为 `YYYY-MM-DD`；无法解析时为空字符串。
- `tags` 是数组；数据库里是逗号分隔也没关系，API 层拆开。
- `title` 为空时回退到 `dlsite_id`。
- `cover_url` 可以是 DLsite 的绝对 URL；Lutris 直接下载，不需要鉴权。

参考 SQL（`latest_file`）：

```sql
SELECT f.id, f.file_name AS name, f.file_size AS size, f.sha256,
       COALESCE(NULLIF(r.label, ''), r.release_date) AS version,
       r.source
FROM releases r
JOIN files f ON f.release_id = r.id
WHERE r.dlsite_id = ?1
ORDER BY (r.source = 'dlsite') DESC, r.release_date_key DESC, r.id DESC
LIMIT 1;
```

## GET /api/v1/works/{dlsite_id}

返回单个作品，字段与列表项相同，额外带 `versions`：

```json
{
  "dlsite_id": "RJ01234567",
  "title": "作品名",
  "latest_file": { "...": "同上" },
  "versions": [
    {
      "release_id": 7,
      "version": "2024-05-01",
      "source": "dlsite",
      "release_date": "2024-05-01",
      "changelog": "……",
      "file": {
        "id": 42,
        "name": "RJ01234567.zip",
        "size": 123456789,
        "sha256": "……"
      }
    }
  ]
}
```

`versions` 是给以后“选版本安装”预留的；当前 Lutris 模块只用 `latest_file`。
`file` 可以为 `null`。

## GET /api/v1/files/{file_id}

返回原始文件：

- 必须支持 `Range`（断点/多线程下载）；
- `Content-Disposition: attachment; filename="..."` 使用原文件名；
- `Content-Type: application/octet-stream`；
- 建议加 `X-Checksum-Sha256`，方便客户端校验。

`file_id` 是 zfsc `files.id`，不是 release id。

## 错误

| 状态码 | 含义 | Lutris 行为 |
| --- | --- | --- |
| `401` | token 缺失/失效/被撤销 | 提示重新连接 |
| `403` | token 权限不足 | 提示重新连接 |
| `404` | 作品或文件不存在 | 安装时提示不可用 |
| `5xx` | zfsc 内部错误 | 显示错误，保留 token |

## Token 管理

最小实现可以只做 CLI：

```bash
zfsc token mint --user alice --name lutris
zfsc token list
zfsc token revoke <id>
```

Token 只显示一次；数据库存 `hash(SESSION_SECRET || token)`。撤销后立即生效。

## 冒烟测试

```bash
export ZFSC_URL=https://zfsc.example.com
export ZFSC_TOKEN=zfsc_...

curl -fsS -H "Authorization: Bearer $ZFSC_TOKEN" "$ZFSC_URL/api/v1/me"
curl -fsS -H "Authorization: Bearer $ZFSC_TOKEN" \
  "$ZFSC_URL/api/v1/works?page=1&per_page=2&with_files=1"
curl -fL -H "Authorization: Bearer $ZFSC_TOKEN" \
  -o /tmp/zfsc-test.bin "$ZFSC_URL/api/v1/files/42"
```
