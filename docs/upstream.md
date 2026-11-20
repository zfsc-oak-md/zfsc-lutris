# 上游与补丁

## 固定版本

`Makefile` 里的 `LUTRIS_REF` 固定为：

```text
eace36e97bd0e4d65bcb361b0d785d75433c65e9
```

这是验证过 `apply.sh` 和 `zfsc.py` 的 Lutris 提交。`scripts/fetch-lutris.sh`
按这个提交做浅克隆；重复执行 `make fetch` 会丢弃工作区改动并重新 checkout，
所以不要把本地修改直接留在 `build/lutris` 里。

## 升级步骤

```bash
# 1. 改 Makefile 里的 LUTRIS_REF
$EDITOR Makefile

# 2. 重新拉取并应用
make fetch
make apply

# 3. 检查
make check
./build/lutris/bin/lutris

# 4. 手动回归：
#    - 连接 zfsc
#    - 刷新列表
#    - 安装一个有官方文件的作品
#    - 安装一个只有非官方文件的作品
#    - 删掉本地 token 文件或刷新 Key 后确认会重新弹连接窗口
```

如果上游改了 `lutris/services/__init__.py` 的结构，`scripts/apply.py` 会报错
而不是静默写坏文件。按提示调整插入点即可。

## 向上游提 PR

这个 overlay 的最终目标仍然是把服务合进 Lutris。提交时：

1. 复制 `lutris/services/zfsc.py` 到 Lutris 源码树；
2. 应用 `patches/0001-register-zfsc-service.patch`；
3. 跑 Lutris 的 `ruff` / `pylint` / `mypy` / `pytest`；
4. 在 PR 说明里写清楚：
   - 这是 self-hosted 服务，服务器地址由用户在连接窗口里填写；
   - 只读，不改用户库；
   - 下载使用用户自己的 zfsc token，不绕过任何 DRM；
   - 失败时回退到手动选择文件（`N/A:` 占位）；
   - 代码按 GPL-3.0 提交。

上游可能提出的问题：

- 是否应该做成通用 “self-hosted library” 服务，而不是绑定 zfsc？
- 没有 lutris.net 的 installer，如何匹配已安装游戏？
  答案：Lutris 按 `games.service_id == service_games.appid` 合并，不需要 lutris.net。
- 服务图标要不要补一个（目前侧栏用 Lutris 默认图标）、是否需要翻译？
- 多版本安装什么时候支持？

## 补丁说明

`patches/0001-register-zfsc-service.patch` 只改
`lutris/services/__init__.py`：

- 增加 `from lutris.services.zfsc import ZfscService`；
- 在 `_services` 字典里增加 `"zfsc": ZfscService`。

模块文件本身由 `scripts/apply.sh` 复制，不放在补丁里，避免同一份代码维护两遍。
需要生成上游用的完整补丁时，先复制模块，再用 `git diff` 生成即可。

## Flatpak

flatpak 构建不编译 Lutris，而是在 Flathub 的 `net.lutris.Lutris` 上叠一个模块，
因此不需要在这里固定和验证 Lutris 源码的每个提交；但建议让 `LUTRIS_REF` 和
base app 里的 Lutris 版本保持一致。流程见 [docs/flatpak.md](flatpak.md)。

