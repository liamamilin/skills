# 已跑通的本机工具与可选投稿

以下是 2026-11-10 本次项目的已知路径，不是对其他电脑的保证。先检查存在性；不存在时使用可用的本机工具或说明缺项。不要自动下载安装大模型或重新部署已有服务。

## 本机运行环境

工作区：本机视频 workflow 仓库的根目录

- FFmpeg / ffprobe：`autovideo/g0/darwin_arm64/ffmpeg` 与 `ffprobe`（相对工作区）。
- 普通 `python3` 已能运行 Pillow、numpy、soundfile。
- 对齐 Python：`autovideo/g3/data/voice-runtime/bin/python`。
- 离线模型：`autovideo/g3/data/voice-models/qwen3-forced-aligner-0.6b-8bit`。
- MLX 需要本机 Metal；如受执行沙箱限制，按工具权限机制运行相同本地脚本，不改成把文件上传到未知服务。
- 本案例中文字体：`/System/Library/Fonts/Hiragino Sans GB.ttc` 的 index 2（W6）；英文字体 Arial Bold。字体不打包，换机器时选择可用字体并实际检查中文，不假设字体文件名就等于预期字形。
- 默认作品可放在工作区忽略的 `autovideo/g3/data/<作品>-<日期>-vN/`，交付副本可放用户配置的成片目录。遵循当前项目的存储约定，交付时注明实际位置。

命令形状（把变量替换为本次真实绝对路径）：

```sh
python3 "$SKILL/scripts/prepare_project.py" --audio "$SONG" --lyrics "$LYRICS" --out "$PROJECT" --ffmpeg "$FFMPEG" --ffprobe "$FFPROBE"
"$ALIGN_PYTHON" "$SKILL/scripts/align_lyrics.py" --project "$PROJECT" --model "$ALIGN_MODEL" --transcript "$TRANSCRIPT"
python3 "$SKILL/scripts/check_video.py" --video "$VIDEO" --out "$QA_REPORT" --expected-duration 69 --cues "$CUES" --cast "$CAST" --source-audio "$SONG" --ffmpeg "$FFMPEG" --ffprobe "$FFPROBE"
```

69 只是本案例最终长度，其他作品必须改为真实剪辑长度。这些工具不是一键创作引擎：助手仍需编排、实现并检查本作品的渲染。

## 用户明确要求投稿时

本次通过 **现有研映项目的本地视频导入 + B 站原生队列** 投稿，未恢复音乐栏目、未新增调度、未改全局策略。仅制作视频不运行本节。

项目路径：工作区下 `AI_research/Base_CodingCLi`。先读该模块当前 `AGENTS.md` 和相关实现，已有接口可能演进。Python 为相对该模块的 `../.AI_research/bin/python`。

投稿和封面修改全程走现有 workflow，不操控浏览器或系统文件选择器。使用当前应用入口：`POST /api/assistant/local-video`，请求模型 `web/services/local_video.py::LocalVideoRequest`；`prepare` 导入/复用与保存草稿，`submit` 进入所指定平台队列。使用应用已有认证，勿伪造会话或泄漏凭证。用户已经明确要求投稿且资料齐全时不重复索要确认。

本次等价地使用了项目公开服务函数：

1. 从模块目录运行，`store.use_state_dir(get_settings().paths.state_dir)` 使用实际已有状态目录。
2. `platform_manager.account()/verify()/categories()` 核对已连接账号、授权、实时分区；不要打印 credentials 或整份配置。`categories()` 可能返回 stale 缓存，选择时区分。
3. `local_video.import_video(最终绝对路径, actor)` 按文件指纹复用；不要创建虚构研究文稿或重渲染。
4. 按 [剧情封面](story-covers.md) 分别制作 4:3、16:9 文件。`POST /api/assistant/local-video` 在原请求中增加 `"covers": {"4x3": "封面4x3的绝对路径.png", "16x9": "封面16x9的绝对路径.png"}`；支持 `prepare` 和 `submit`。已有 render 则调用 `PUT /api/platforms/bilibili/covers/{render_id}/paths`，JSON 为 `account_uid`、`cover_4x3`、`cover_16x9`。等价服务函数为 `bilibili_covers.import_paths(render_id, {"4x3": path43, "16x9": path169})`。入口会检查比例、保留原构图并登记不可变 PNG 资产；不要只向目录复制图片。用 `bilibili_covers.preview(render)` / `GET /api/platforms/bilibili/covers/{render_id}` 核对两张采用图。队列将 16:9 传入 `cover`，4:3 上传后经 biliup `--extra-fields` 传入 `cover43`，同一次投稿提交。
5. 保存标题、简介、标签、tid 的发布草稿（`distributions.save_draft`），再 `platform_manager.enqueue(render_id, fields + account_uid)`，沿用项目的去重与队列。首评沿用当前项目的默认模板与设置，用户本次明确指定时采用其要求；不要把历史模板或开关硬编码。
6. 项目已运行的 worker 处理任务。不要为了这一条调用会顺带操作其他任务的全局 tick；服务不可用时按其启动方式恢复用户所需能力，不改变调度策略。
7. 读取这一个任务状态；出现 UNKNOWN 先核对，不重复上传。收到 SUBMITTED 和 BV 号即可报告“已投稿，待审核”；只有平台确认公开后才说已发布。双比例检查读取 `BilibiliClient.archive_for_edit(bvid)` 的 `archive.cover` 与 `archive.cover43`；平台会更换 CDN 主机，以文件 URL 路径对应采用图片。图已上传不等于稿件已采用。缺图或需补换时调用下节 workflow 更新入口，不重投视频、不重复发送首评。保留回执。

如果上述服务不再适用，阅读当前 API 后适配，不复制旧凭证、不绕过登录、不新造发布器。出现缺少明确标题/简介时，可沿用当前作品已经确定的信息；真正缺少时只询问缺项。

本案例当时实时分区为「音乐 / AI音乐」tid 265。这些是历史记录，不应硬编码为下一条作品的账号或分区。投稿记录对应 BV1kJW36aEWq；不要因重跑 skill 再次投稿。

## 修改已发布 B 站封面

2026-11-11 已接入项目 API 和 B 站发布页：展开既有投稿的“修改双比例封面”，分别选择两图并更新。助手直接使用下列 workflow API / 服务函数，不操控浏览器；服务报错时保留回执、修复或说明阻塞，不切换网页手工投稿。

1. 根据项目投稿记录找到目标作品的 `task_id`、`render_id`、BV 与当前 `account_uid`。只修改用户要求的作品；历史案例不是默认修改目标。
2. 先经上节 `/covers/{render_id}/paths` 或 `bilibili_covers.import_paths` 登记两张图。队列已保存的图片不会被改写，新任务用最新选择；已有稿件需执行下一步才会更新平台。
3. `POST /api/platforms/bilibili/uploads/{task_id}/covers`，JSON：`{"account_uid": "当前账号UID"}`。等价服务函数：`bilibili_covers.update_published(task_id, account_uid)`。它读取原稿信息，上传两图，更新同一 BV，保留原有分 P 的 CID、标题、简介、标签和设置。不得重新调用视频 submit 来换封面。
4. `CONFIRMED` 表示平台回读两张封面已对应；`SUBMITTED` 表示修改已接受但尚未回读确认；`UNKNOWN` 表示请求结果未确认。后两者先查回执和原稿，不重投视频。重复调用会先回读已有封面，已经对应时不重复编辑。
5. 保存作品回执与两张采用图。项目回执在 `state/platforms/bilibili/uploads/{task_id}/cover-edit.json`，更新前稿件快照在同目录 `cover-edit-before-*.json`。不要把 Cookie 或授权信息写进交付材料。

实测案例：《我还在优化》`BV1cNW26fEwZ`，两张图均由 workflow 上传、更新并回读确认；原 CID、标题、简介、标签、评论、字幕和水印设置保持不变。代码与验收记录：项目 `spec/acceptance/bilibili-dual-covers-20261111/`。新投稿的双图传递经过本地导入→队列→原生 CLI 的隔离测试，未为了验收重复公开投稿。

接口踩坑：创作中心返回的是展示模型，不能直接整体回传。`human_type2.id`、`recreate.switch` 转为编辑用整数；`creation_statement` 保持对象，不能只传其 id，否则真实接口报 21001。上述差异已封装在 workflow，skill 不自行另造发布器。
