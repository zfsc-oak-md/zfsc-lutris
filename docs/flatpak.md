# Flatpak

`flatpak/io.github.zfsc_oak_md.ZfscLutris.yml` 把 ZFSC 服务打进一个独立的
Flatpak 应用，方便 Steam Deck、Silverblue 这类不方便改系统 Lutris 的用户。

## 为什么是独立 app id

应用 id 是 `io.github.zfsc_oak_md.ZfscLutris`，不是 `net.lutris.Lutris`：

（GitHub org 是 `zfsc-oak-md`，但 flatpak/D-Bus 只允许最后一段带 `-`，非最后一段
用 `_`，所以是 `zfsc_oak_md`。）

- 可以和官方 Flathub 版 Lutris 共存，升级官方版不会冲掉补丁；
- 数据目录独立（`~/.var/app/io.github.zfsc_oak_md.ZfscLutris`），不会和官方版
  抢同一个 ref；
- 代价是需要迁移一次配置，见下面「从官方 Lutris 迁移」。

只提供 `x86_64`：底层的 `org.winehq.Wine` 没有 aarch64。

## 构建方式

manifest 用 `base: net.lutris.Lutris`，构建时把 Flathub 官方 app 的 `/app`
复制过来，然后只做三件事：

1. 用 `scripts/apply.py` 往 `site-packages/lutris/services/` 里加 `zfsc.py` 并注册；
2. 装一个启动脚本 `zfsc-lutris`，首次运行时把服务图标放进 Lutris 的 runtime 目录；
3. 换上本项目的 desktop 文件和 AppStream 元数据。

所以不需要编译 Lutris、Wine、VLC，一次构建几分钟。`finish-args` 和
`add-extensions` 是从 Flathub manifest 抄过来的，上游换 runtime 时要同步。

## 本地构建

依赖：

```bash
# 发行版包
flatpak flatpak-builder
# GNOME runtime、SDK，以及作为 base 的官方 Lutris
flatpak remote-add --if-not-exists --user flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.gnome.Sdk//51 org.gnome.Platform//51 net.lutris.Lutris//stable
```

然后：

```bash
make flatpak
```

产物：

- `build/flatpak-repo/`：本地 flatpak 仓库；
- `build/io.github.zfsc_oak_md.ZfscLutris.flatpak`：单文件 bundle。

当前验证过的组合：Flatpak 1.18、flatpak-builder 1.4.12、Flathub 上的
Lutris 0.5.23（x86_64）；构建产物约 983 MB。

如果宿主机没装 `flatpak-builder`，可以在 Flathub 的 Flatpak Builder 里构建
（注意 `FLATPAK_USER_DIR` 要指向宿主机的用户安装，沙箱里的 `$HOME` 不是宿主机
home）：

```bash
flatpak install --user flathub org.flatpak.Builder
flatpak run --command=bash org.flatpak.Builder -lc \
  'export FLATPAK_USER_DIR=/var/home/$USER/.local/share/flatpak
   cd /var/home/$USER/wksp/zfsc-lutris && ./scripts/build-flatpak.sh'
```

构建脚本总是带 `--disable-rofiles-fuse`：模块需要修改从 base app 复制来的
`lutris/services/__init__.py`，而 rofiles-fuse 会把这类文件的写入挡掉。

安装：

```bash
flatpak install --user --bundle build/io.github.zfsc_oak_md.ZfscLutris.flatpak
```

运行时不需要安装官方 Lutris（构建时用到的 `/app` 已经复制进来了），但需要
Flathub 的 GNOME runtime 和 Wine 相关扩展。

如果想让本地仓库参与更新：

```bash
flatpak remote-add --user --if-not-exists --no-gpg-verify \
  zfsc-local "file://$PWD/build/flatpak-repo"
flatpak install --user zfsc-local io.github.zfsc_oak_md.ZfscLutris
```

设了 `FLATPAK_GPG_KEY` 时构建脚本会用该 key 签名仓库和 bundle，此时去掉
`--no-gpg-verify`。

## 公开发布

`.github/workflows/flatpak.yml` 在 `flatpak-v*` tag 或手动触发时：

1. 安装 runtime 和官方 Lutris；
2. 用 secret `FLATPAK_GPG_PRIVATE_KEY` 导入签名 key，key ID 用
   `FLATPAK_GPG_KEY_ID`；
3. 构建并签名仓库；
4. 生成 `.flatpakref`（内嵌公钥和 Pages 地址），部署到 GitHub Pages；
5. tag 构建时把 `.flatpak` bundle 附到 release。

仓库需要先做两件设置：

- **Settings → Pages → Source** 选 *GitHub Actions*；
- 添加上面两个 secret。

用户安装：

```bash
flatpak install --user --from \
  https://zfsc-oak-md.github.io/zfsc-lutris/io.github.zfsc_oak_md.ZfscLutris.flatpakref
```

之后 `flatpak update` 就会跟随仓库更新。

### 签名 key

CI 里的签名 key 需要免密码（flatpak 签名走 gpg，不方便交互输入密码）：

```bash
gpg --quick-gen-key "ZFSC Lutris signing <zfsc@example.com>" rsa4096 sign never
gpg --armor --export-secret-keys <KEY_ID> > key.asc   # 放进 FLATPAK_GPG_PRIVATE_KEY
```

`FLATPAK_GPG_KEY_ID` 填 key ID。这个 key 只用于签名 flatpak 仓库，泄露后换新
key、更新 `.flatpakref` 里的公钥即可。

### 托管容量

GitHub Pages 有 1GB 站点上限。官方 Lutris 的下载体积约 325 MB、安装后约 1 GB，
我们的 app 内容与之相同，正常情况下仓库能放进 Pages；但为了留余量：

- 构建脚本对仓库执行 `build-update-repo --prune`，只保留最新版本；
- 如果以后超出限制，把 `build/flatpak-repo` 原样同步到对象存储（例如
  Cloudflare R2）或自己的静态站，只改 `.flatpakref` 里的 `Url` 即可，
  仓库格式不用变。

## 从官方 Lutris 迁移

游戏列表和设置在 Lutris 的数据目录里，复制过来即可：

```bash
old="$HOME/.var/app/net.lutris.Lutris"
new="$HOME/.var/app/io.github.zfsc_oak_md.ZfscLutris"

mkdir -p "$new/data/lutris" "$new/config"
# Lutris 在没有 ~/.config/lutris 时会把配置放在 data/lutris，两种位置都要照顾到
for item in pga.db lutris.conf games banners coverart; do
  cp -a "$old/data/lutris/$item" "$new/data/lutris/" 2>/dev/null || true
done
cp -a "$old/config/lutris" "$new/config/" 2>/dev/null || true
cp -a "$old/data/icons" "$new/data/" 2>/dev/null || true

# 可选：图标缓存和 ZFSC 的 token，省得重新登录
cp -a "$old/cache/lutris" "$new/cache/" 2>/dev/null || true
```

`runners/` 和 `runtime/` 没有复制，新 app 会按需重新下载。游戏本体和 Wine
prefix 的路径保存在配置里：如果它们本来就在宿主机路径（例如 `~/LutrisGames`），
两个 app 都能直接用；如果放在 `~/.var/app/net.lutris.Lutris/` 下面，需要把那些
目录一并移到新 app 目录，或者在游戏配置里把路径改到宿主机目录。

复制完先不要卸载官方版，确认新 app 里游戏都能启动、prefix 路径没问题之后再清理
旧数据。

## 版本同步

- base app 是 Flathub 上的 `net.lutris.Lutris//stable`。上游更新后，重新构建即可
  带上新版本；`scripts/build-flatpak.sh` 会打印本次使用的 base commit。
- 想固定 base 版本时，设 `FLATPAK_BASE_COMMIT`（CI 里是仓库变量
  `FLATPAK_BASE_COMMIT`），构建会在这个 commit 不匹配时直接失败。
- 如果 Flathub 升级了 runtime（当前是 `org.gnome.Platform//51`）或改了
  `finish-args` / `add-extensions`，需要同步 manifest 顶部和
  `flatpak/io.github.zfsc_oak_md.ZfscLutris.yml` 里的对应块。
- 建议同时把 `Makefile` 的 `LUTRIS_REF` 对齐到 base app 里的 Lutris commit
  （`flatpak info --show-commit net.lutris.Lutris//stable`），保证源码安装和
  flatpak 验证的是同一版本。

每次升级后的回归清单：

- 连接 zfsc、刷新列表；
- 安装一个有官方文件的作品；
- 安装一个只有非官方文件的作品；
- 左侧 ZFSC 图标正常显示（首次启动的图标铺设逻辑）；
- `flatpak update` 后 token 仍然有效。

## 已知问题

- **自签 HTTPS**：沙箱里没有系统的 CA。可以给 app 加环境变量指向宿主机的
  CA 文件（`--filesystem=home` 已经允许读取）：

  ```bash
  flatpak override --user --env=REQUESTS_CA_BUNDLE="$HOME/certs/zfsc-ca.pem" \
    io.github.zfsc_oak_md.ZfscLutris
  ```

- **图标**：Lutris 只从 `runtime/icons` 找服务图标，由 `zfsc-lutris` 启动脚本
  在首次运行时复制。直接 `flatpak run --command=lutris ...` 不会执行这段逻辑。
- **下载目录**：下载和安装都在沙箱的 home 权限内，和官方 Lutris 行为一致。
- **和官方版同时启用 DLsite**：同一个作品可能出现两次。ZFSC 的 appid 就是
  RJ/VJ 号，一般只启用 ZFSC 即可。
