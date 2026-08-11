# DeepSeek 模型配置说明

本工作流**只使用 DeepSeek 模型**。以下配置已在本机完成。

## 全局配置（~/.pi/agent/settings.json）

```json
{
  "defaultProvider": "deepseek",
  "defaultModel": "deepseek-v4-flash",
  "defaultThinkingLevel": "high"
}
```

## API Key（全局 ~/.pi/agent/auth.json，非项目 .pi/）

```json
{
  "deepseek": "<你的 DeepSeek API Key>"
}
```

配置方式：
```bash
pi auth   # 交互式配置，选择 deepseek provider 粘贴 key
```
或直接编辑 `~/.pi/agent/auth.json`。

> ⚠️ **`~` 指用户主目录**（Windows 上如 `C:\Users\<你的用户名>`），
> 即 `C:\Users\<你的用户名>\.pi\agent\auth.json`——**不是**项目目录下的 `.pi\`。
>
> 两处 `.pi` 的区别：
>
> | 位置 | 路径 | 内容 |
> |------|------|------|
> | 全局 | `~/.pi/agent/auth.json` | **API Key**（所有项目共用，仅在全局一处存放） |
> | 项目内 | `<项目>/.pi/settings.json` | 模型锁定配置（无密钥，可安全提交到 git） |
>
> **安全原则**：密钥只存在全局一处，项目内 `.pi/` 不应存放密钥——
> 这样无论项目怎么 git 推送，密钥都不会进仓库。

## 模型目录（~/.pi/agent/models-store.json）

已注册模型：

| id | 名称 | 用途 |
|----|------|------|
| `deepseek-v4-flash` | DeepSeek V4 Flash | 默认：日常开发、快速迭代 |
| `deepseek-v4-pro` | DeepSeek V4 Pro | 备选：复杂推理、长任务 |

两个模型均：
- API：OpenAI 兼容（`https://api.deepseek.com`）
- 支持思考模式（thinkingFormat: deepseek）
- 上下文 1M / 最大输出 384K tokens

## 项目级锁定（PIVibeCoding/.pi/settings.json）

在 `PIVibeCoding` 目录启动 Pi 时自动生效，
确保本工作流环境不混用其他厂商模型：

```json
{
  "defaultProvider": "deepseek",
  "defaultModel": "deepseek-v4-flash",
  "defaultThinkingLevel": "high"
}
```

## 切换模型

```bash
# 会话内切换
/model deepseek-v4-pro

# 或改 settings.json 的 defaultModel
```

## 验证配置是否生效

启动 Pi 后输入：
```
/model      # 查看当前模型，应显示 DeepSeek
```

或检查侧边栏/状态栏的模型名。
