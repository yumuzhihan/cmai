# `cmai config` 交互式配置规划

## 目标与边界

- 实现 `cmai config`，管理全局配置文件 `~/.config/cmai/settings.env`；本期不改变 `cmai commit --config <path>` 的自定义配置文件语义。
- 首次运行：仅在用户完成并确认保存后创建父目录和配置文件。
- 已有配置：先展示路径和已配置项（`API_KEY` 始终脱敏），再由用户选择「完整重新配置」「只改 Provider」「只改 Commit 规范」「只改可选项」或退出。未选择的字段必须原样保留。
- 所有交互使用 Click，支持非交互环境以明确错误退出；不打印密钥、模板全文中的敏感内容或无关环境变量。

## 0. 先消除现有配置加载的副作用

- [ ] 在 `cmai/config/settings.py` 提取 `DEFAULT_SETTINGS_PATH = Path.home() / ".config" / "cmai" / "settings.env"`，供命令和 `Settings` 共用。
- [ ] 删除 `Settings.Config` 类定义期间的 `mkdir()` 与 `touch()`。当前 `cmai` 在载入 CLI 子命令时就导入 `settings`，导致 `cmai config` 无法可靠判断配置文件是否原本存在。
- [ ] 保持「配置文件不存在时使用 `Settings` 默认值」的读取行为；只把创建文件的职责交给保存函数。`load_from_env()` 对不存在路径应保持无异常。

## 1. 配置文件读写层

- [ ] 在 `cmai/cli/commands/config.py`（或为便于测试抽出的同包 helper）实现：读取现有 `.env`、合并本次修改、原子写回、重新载入内存中的 `settings`。
- [ ] 写回时保留不由本命令管理的键、注释和空行；本期只更新下列托管键，避免 `config` 覆盖用户手写的日志、重试和 diff 参数：
  - Provider：`PROVIDER`、`API_BASE`、`API_KEY`、`MODEL`，以及 Ollama 兼容项 `OLLAMA_HOST`。
  - Commit：`COMMIT_STRICT`、`COMMIT_SPEC`、`COMMIT_ALLOWED_TYPES`、`COMMIT_SCOPE_POLICY`、`COMMIT_SUBJECT_MAX_LEN`、`COMMIT_HEADER_MAX_LEN`、`COMMIT_SUBJECT_CASE`、`COMMIT_ALLOW_BANG`。
  - 可选：`PROMPT_TEMPLATE`、`RESPONSE_LANGUAGE`。
- [ ] 密钥保存前校验为单行非空文本；写入成功后设置文件权限为仅当前用户可读写（POSIX `0600`，Windows 跳过权限断言）。保存前显示脱敏摘要并要求确认；取消或中断时不写文件。
- [ ] 对空值采用清晰、一致的规则：编辑 Provider 时可清除 `API_BASE` / `API_KEY` / `MODEL`，配置文件中移除对应键，让 SDK 默认值或外部环境变量继续生效；其他字段使用默认值作为提示值。

## 2. 入口与交互总流程

- [ ] `config_command()` 先检查 `DEFAULT_SETTINGS_PATH.exists()`，再读取当前值；不可读或格式错误时给出路径与错误，且不覆盖原文件。
- [ ] 文件不存在时进入完整向导：Provider → Commit 规范 → 可选配置 → 脱敏预览 → 确认保存。
- [ ] 文件存在时显示当前状态并提供菜单：
  1. 完整重新配置（依次执行全部三个分区）；
  2. Provider；
  3. Commit 规范；
  4. 可选配置；
  5. 退出不保存。
- [ ] 分区编辑以当前有效配置为默认值；保存后输出配置路径、已更新字段和「下次 `cmai` 生效」提示，绝不回显 API key。

## 3. Provider 分区

- [ ] 在启动选择器前实例化 `ProviderFactory`，通过 `list_providers()` 动态取得已经成功注册的 Provider；按名称排序并直接使用注册键作为 `PROVIDER` 的候选值，不在 CLI 中重复维护 Provider 列表。
- [ ] 选择后依次配置 `API_BASE`、`API_KEY`（隐藏输入）和 `MODEL`。每项展示当前值或 provider 的已有默认值；`API_BASE` 标注为可选、自定义或代理端点才需要。
- [ ] Ollama 没有 API key 要求，界面仍允许跳过 `API_KEY`，并将「API Base」同时兼容为连接地址：更新 `OllamaProvider` 的主机解析优先级为 `OLLAMA_HOST` → `API_BASE` → `http://localhost:11434`。这样用户按统一字段配置 `API_BASE` 时可真正生效，历史 `OLLAMA_HOST` 配置不受影响。
- [ ] 如果可选依赖未安装、Factory 未注册任何 Provider，显示可操作的安装提示并以非零退出，不创建半成品配置。

## 4. Commit 规范分区

- [ ] 先询问 `COMMIT_STRICT`：开启时，生成结果未通过校验将不能直接提交；关闭时仅保留校验结果，不阻断提交。
- [ ] 让用户选择 `COMMIT_SPEC`：`conventional` 或 `angular`，与 `resolve_commit_rules()` 当前支持范围一致。
- [ ] 提供「使用规范默认规则」与「调整详细规则」两级选择。详细规则覆盖全部现有校验字段：
  - 逗号分隔的 `COMMIT_ALLOWED_TYPES`（留空时删除该键并回退规范默认类型）；
  - `COMMIT_SCOPE_POLICY`：`optional` / `required` / `forbid`；
  - 正整数 `COMMIT_SUBJECT_MAX_LEN`、`COMMIT_HEADER_MAX_LEN`；
  - `COMMIT_SUBJECT_CASE`：`lower` / `sentence` / `any`；
  - `COMMIT_ALLOW_BANG`。
- [ ] 对数字和 choice 值在输入阶段校验；将规则摘要（包括最终允许类型和长度）展示给用户，确保配置含义与 `resolve_commit_rules()` / `validate_commit_message()` 一致。

## 5. 可选配置分区

- [ ] `RESPONSE_LANGUAGE` 使用普通文本输入，默认保留当前值（默认 `English`），并拒绝空字符串。
- [ ] `PROMPT_TEMPLATE` 提供「保留当前」「恢复内置默认」「在 `$EDITOR` 中编辑」三个选项。编辑器取消或未修改时保留原模板；没有可用编辑器时说明原因并不保存模板改动。
- [ ] 统一模板变量为实际渲染器支持的 `{user_input}`、`{diff_content}`、`{language}`，并在保存前验证三个占位符都存在。当前 `Settings` 默认值使用了双花括号，而 `Normalizer` 用单花括号替换，需同步修正默认模板，并在首次编辑旧值时提示迁移或兼容替换双花括号。
- [ ] 因 `.env` 不适合直接保存换行文本，为模板定义可逆编码方案（例如 JSON 字符串），并在加载路径解码；同时兼容旧版纯文本 `PROMPT_TEMPLATE`。不要把真实换行写成多条伪 `.env` 记录。

## 6. 测试与文档

- [ ] 新增 `CliRunner` 测试，使用临时 `HOME`/配置路径覆盖：首次运行不在确认前创建文件、确认后创建并写入；已有配置的完整/三种局部编辑；退出与 Ctrl-C 均不改文件。
- [ ] 覆盖 Provider 列表来自 Factory、API key 不出现在输出、未知/缺失 Provider、Ollama 的 `API_BASE` fallback、设置保存后重新加载。
- [ ] 覆盖 Commit 的 strict 开关、两种规范、详细规则输入校验和「留空回退默认类型」。
- [ ] 覆盖模板编辑/取消、占位符校验、模板编码往返以及旧双花括号模板的兼容迁移；补充 `Settings` 不再在 import 时创建文件的回归测试。
- [ ] 更新 `README.md`：用 `cmai config` 替代手动创建配置的主路径，说明配置文件位置、三个分区、Provider 依赖安装方式、API key 的安全提示、模板变量及 `--config` 仍用于临时自定义文件。

## 验收标准

- [ ] `cmai config` 的首次执行能完成三个分区并在确认后生成可被 `cmai commit` 读取的配置。
- [ ] 再次执行能完整重配或只改任一分区，未编辑字段和非托管 `.env` 内容不被损坏。
- [ ] Provider 选项与实际已注册 Provider 一致，Ollama、远程 Provider 的端点与密钥行为正确。
- [ ] 严格校验、提交规范、语言和模板修改都能影响后续生成；无效输入、编辑取消和写入失败不会留下部分配置。
