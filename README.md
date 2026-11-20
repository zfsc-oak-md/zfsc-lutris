# zfsc-lutris

把自建 [zfsc](https://github.com/zfsc-oak-md/zfsc) 作为 Lutris 的游戏源接入。

这个仓库不是 Lutris 的 fork，而是一个 **overlay**：

- `lutris/services/zfsc.py` 是服务模块，逻辑对标 Lutris 自带的 `dlsite.py`；
- `scripts/apply.sh` 把模块复制进上游 Lutris 源码树，并注册到 `lutris/services/__init__.py`；
- `patches/0001-register-zfsc-service.patch` 是注册改动的参考补丁；
- `docs/zfsc-api.md` 是 zfsc 侧需要实现的 `/api/v1` 契约。

这样上游更新时只需要重新 fetch + apply，不用维护一整棵 Lutris 源码。

## 依赖

- Lutris 的运行依赖（GTK3、WebKit2、Wine 等），见 [Lutris 下载页](https://lutris.net/downloads) 或上游仓库的安装说明。
- 一个已经实现 `/api/v1` 的 zfsc 实例。接口定义见 [docs/zfsc-api.md](docs/zfsc-api.md)。
- 一个 zfsc API Token。

## 快速开始

```bash
git clone git@github.com:zfsc-oak-md/zfsc-lutris.git
cd zfsc-lutris

make fetch     # 拉取固定版本的 Lutris 源码到 build/lutris
make apply     # 复制 zfsc.py、注册服务、安装图标
make run       # 从源码运行 Lutris
```

`make apply` 默认把图标装到 `~/.local/share/lutris/runtime/icons/hicolor/scalable/apps/zfsc.svg`。
如果 Lutris 配置了自定义 runtime 目录，用：

```bash
LUTRIS_RUNTIME_DIR=/path/to/runtime make apply
```

也可以手动应用到一个已有的 Lutris 源码树：

```bash
./scripts/apply.sh /path/to/lutris
```

如果 Python 依赖装在 `$HOME` 下（`pip --user`，或 Lutris 本身装在 `~/.local`），
上游 `bin/lutris` 默认会把 `$HOME` 从 `sys.path` 中剔除，`make run` 会报
`No module named '...'`。这种环境显式放开：

```bash
LUTRIS_ALLOW_LOCAL_PYTHON_PACKAGES=1 make run
```

## 配置

1. 在 zfsc 服务器上生成 token（普通 viewer 可以让管理员代跑）：

   ```bash
   zfsc token mint --user alice --name lutris
   ```

2. 启动 Lutris，打开 **Preferences → Sources**，启用 **ZFSC**，按提示重启 Lutris。
3. 左侧栏点击 **ZFSC**，点刷新按钮；第一次会弹出连接窗口，填入：
   - Server URL，例如 `https://zfsc.example.com`
   - API token
4. 刷新成功后，zfsc 中所有有文件的作品会出现在 ZFSC 列表里。

安装时 Lutris 会直接向 `/api/v1/files/{id}` 发起带 `Authorization: Bearer` 的下载请求，
然后按普通 Wine 游戏安装（`create_prefix` + `install_or_extract`）。

## 当前能力

- 同步 zfsc 作品列表（只包含有文件的作品）
- 封面
- 安装最新官方版本；没有官方文件时回退到最新非官方版本
- DLsite 商品页链接

暂不支持：

- 多版本选择（zfsc 页面上的每个 release）
- 游戏更新检查
- DLC / 特典
- Linux 原生版本识别（统一按 Wine 处理）

## 和 DLsite 服务的关系

zfsc 的 `appid` 就是 DLsite 的 RJ/VJ 号。如果同时启用 Lutris 自带的 **DLsite** 服务和 **ZFSC**，
同一个作品会出现两次。一般只启用 ZFSC 即可。

## 更新上游

`Makefile` 里的 `LUTRIS_REF` 固定了验证过的上游提交。升级步骤见 [docs/upstream.md](docs/upstream.md)。

## 许可

本仓库包含参考 Lutris `dlsite.py` / `base.py` 实现的代码，按 GPL-3.0 发布，见 [LICENSE](LICENSE)。
