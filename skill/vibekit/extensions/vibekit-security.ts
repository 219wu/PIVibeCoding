/**
 * vibekit 安全权限门（pi Extension）
 * ==================================
 *
 * 把 vibekit 安全层从"靠模型自觉跑 check-command"升级为"系统强制拦截"：
 *
 * 1. tool_call 拦截：
 *    - bash 命令命中危险模式（rm -rf /、强制推送、drop table 等）→ 直接 block
 *    - write/edit 工具写敏感文件（.env、auth.json、私钥）→ 直接 block
 * 2. 工具级审计：每次工具调用追加到 .vibe/audit.log（比阶段级审计更细）
 *
 * 安装：复制本文件到 ~/.pi/agent/extensions/（全局）或 .pi/extensions/（项目），
 *       pi 自动发现；改后 /reload 生效。
 * 卸载：删除文件即可。
 *
 * 注意：这是"最后防线"——正常流程仍应让模型先跑 security.py check-command
 * （带建议输出）；本 extension 兜底拦截，防模型忘记/绕过。
 *
 * 兼容性：正则全部用 new RegExp 字符串形式（避免 TS 解析器对正则字面量的兼容问题）。
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import * as fs from "node:fs";
import * as path from "node:path";

/** 危险命令模式（移植自 security.py DANGER_COMMANDS） */
const DANGER_COMMANDS: Array<[RegExp, string]> = [
  [new RegExp("git\\s+(push|fetch|pull)[^\\n]*\\s(--force|-f)\\b", "i"), "强制推送/拉取会覆盖远端历史"],
  [new RegExp("rm\\s+(-[rfd]+)?\\s+/(\\s|$)|rm\\s+-rf\\s+~|rm\\s+-rf\\s+[a-z]:\\\\?$", "i"), "删除根目录/家目录/盘符根（不可逆）"],
  [new RegExp("\\bdel\\s+\\/[sq]|\\brd\\s+\\/s\\b|format\\s+[a-z]:", "i"), "Windows 递归删除/格式化"],
  [new RegExp("\\bdrop\\s+(database|table|schema)\\b", "i"), "删除数据库对象"],
  [new RegExp("curl\\s+[^\\n|]*\\|\\s*(ba|z)?sh\\b", "i"), "管道直接执行远程脚本"],
  [new RegExp("git\\s+reset\\s+--hard", "i"), "丢弃所有未提交改动（高危，需确认）"],
  [new RegExp("git\\s+clean\\s+-(f|d|fd|df|fx|xf)\\b", "i"), "删除未跟踪文件（高危，需确认）"],
  [new RegExp("\\b(shutdown|reboot|halt)\\b", "i"), "关机/重启（高危，需确认）"],
];

/** 敏感路径（移植自 security.py SENSITIVE_PATH_PATTERNS） */
const SENSITIVE_PATH_RE = new RegExp(
  "(^|[/\\\\])(auth\\.json|\\.env(\\.|$)|id_rsa|id_ed25519|id_ecdsa|id_dsa|\\.netrc|credentials|secrets?([/\\\\]|$))|\\.(pem|key|p12|pfx|p8|ppk)$",
  "i",
);

/** 工具级审计：追加 .vibe/audit.log（当前工作目录） */
function audit(cwd: string, action: string, detail: string, result: string): void {
  try {
    const dir = path.join(cwd, ".vibe");
    fs.mkdirSync(dir, { recursive: true });
    const ts = new Date().toISOString().slice(0, 19);
    fs.appendFileSync(
      path.join(dir, "audit.log"),
      ts + " | " + action + " | " + detail + " | " + result + "\n",
      "utf-8",
    );
  } catch {
    /* 审计失败不阻断主流程 */
  }
}

/** 从工具输入中提取命令/路径 */
function getCommand(input: Record<string, unknown>): string {
  const c = input.command;
  return typeof c === "string" ? c : "";
}

function getPaths(input: Record<string, unknown>): string[] {
  const out: string[] = [];
  for (const key of ["path", "filePath", "target", "dest"]) {
    const v = input[key];
    if (typeof v === "string") out.push(v);
  }
  return out;
}

function findDanger(command: string): string | null {
  for (const [re, reason] of DANGER_COMMANDS) {
    if (re.test(command)) return reason;
  }
  return null;
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    ctx.ui.notify("vibekit 安全权限门已加载（tool_call 拦截 + 工具级审计 + 模型切换）", "info");
  });

  // ---- 模型分离：审查用 pro，编写用 flash ----
  // 模型可在审查阶段自主调用（比用户手动 /model 强），切换记录进审计日志
  /** 从 models-store.json 读取真实 Model 条目（pi 的 Model 序列化格式）。
   *  不能用 {provider,id} 假对象：切换后模型继续运行时，pi 会读取
   *  model.api/baseUrl/compat/cost 等缺失字段 → includes 崩溃。 */
  const getRealModel = (provider: string, id: string): Record<string, unknown> | null => {
    try {
      const storePath = path.join(os.homedir(), ".pi", "agent", "models-store.json");
      const store = JSON.parse(fs.readFileSync(storePath, "utf8"));
      const list = store?.[provider]?.models;
      if (Array.isArray(list)) {
        const m = list.find((x: { id?: string }) => x.id === id);
        if (m) return m;
      }
    } catch { /* 读不到则回退假对象 */ }
    return null;
  };

  const switchModel = async (modelId: string, label: string) => {
    // 关键：pi.setModel(pro) 内部会用【当前 thinking level】调 setThinkingLevel，
    // 若当前是 low（执行阶段 flash-low 残留）→ pro 上 thinking 解析异常。先升 high。
    if (modelId === "deepseek-v4-pro") {
      try {
        const cur = pi.getThinkingLevel();
        if (cur === "low" || cur === "minimal") {
          pi.setThinkingLevel("high" as never);
          audit(process.cwd(), "thinking_switch", "low->high (先于切 pro)", "ok");
        }
      } catch { /* 忽略 */ }
    }
    const real = getRealModel("deepseek", modelId);
    const target = real ?? { provider: "deepseek", id: modelId };
    const ok = await pi.setModel(target as never);
    audit(process.cwd(), "model_switch", label + " -> " + modelId +
      (real ? " (real model)" : " (fallback fake)"), ok ? "ok" : "FAIL(no api key)");
    return ok;
  };

  pi.registerTool({
    name: "set_review_model",
    label: "Switch to review model",
    description: "Switch the current session model to deepseek-v4-pro for code review " +
      "(model separation: writer flash / reviewer pro). Call this BEFORE starting the " +
      "review phase, then use set_writer_model to switch back after review.",
    parameters: Type.Object({}),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const ok = await switchModel("deepseek-v4-pro", "审查");
      return {
        content: [{ type: "text", text: ok
          ? "已切换到审查模型 deepseek-v4-pro（模型分离生效）。审查完成后调用 set_writer_model 切回。"
          : "切换失败：deepseek 无可用 API key（检查 ~/.pi/agent/auth.json）" }],
        details: {},
      };
    },
  });

  pi.registerTool({
    name: "set_writer_model",
    label: "Switch to writer model",
    description: "Switch the current session model back to deepseek-v4-flash (writer model). " +
      "Call after the review phase is done to restore the default writer model.",
    parameters: Type.Object({}),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      const ok = await switchModel("deepseek-v4-flash", "编写");
      return {
        content: [{ type: "text", text: ok ? "已切回编写模型 deepseek-v4-flash" : "切换失败" }],
        details: {},
      };
    },
  });

  // ---- 思考层级切换（配合模型路由表） ----
  // flash 支持 low/high/max；pro 只有 high/max（pi 自动 clamp）
  pi.registerTool({
    name: "set_thinking_level",
    label: "Set thinking level",
    description: "Set thinking level: low / high / max (auto-clamped to model capability). " +
      "Model routing: conceive high, plan high, isolate low, execute high, verify low, " +
      "review high, integrate low. NOTE: deepseek-v4-pro only supports high/max (pi " +
      "auto-clamps); flash supports low/high/max. Call at phase transitions.",
    parameters: Type.Object({
      level: Type.Union([Type.Literal("low"), Type.Literal("high"), Type.Literal("max")]),
    }),
    async execute(toolCallId, params, signal, onUpdate, ctx) {
      let level = params.level as "low" | "high" | "max";
      // 防御 pi 压缩崩溃：deepseek-v4-pro 只支持 high/max（thinkingLevelMap 仅 high/max），
      // 在 pro 下调 low 会触发 getSupportedThinkingLevels 返回 undefined → includes 崩溃
      try {
        const cur = pi.getModel();
        if (cur?.id === "deepseek-v4-pro" && level === "low") {
          level = "high";
        }
      } catch { /* 忽略 */ }
      pi.setThinkingLevel(level as never);
      audit(process.cwd(), "thinking_switch", level, "ok");
      return {
        content: [{ type: "text", text: "思考层级已切换为 " + level + "（pro 下自动 clamp，审计已记录）" }],
        details: {},
      };
    },
  });

  pi.on("tool_call", async (event, ctx) => {
    const { toolName, input } = event;
    const cwd = process.cwd();

    // ---- 1. bash 危险命令拦截 ----
    if (toolName === "bash") {
      const command = getCommand(input);
      const danger = findDanger(command);
      if (danger) {
        audit(cwd, "tool_blocked", "bash: " + command.slice(0, 120), "DANGER:" + danger);
        return {
          block: true,
          reason: "[vibekit 安全] 危险命令被拦截: " + danger +
            "。如需执行请人工确认，或用更安全的等价命令。",
        };
      }
      audit(cwd, "tool_call", "bash: " + command.slice(0, 100), "ok");
    }

    // ---- 2. 敏感文件写保护 ----
    if (toolName === "write" || toolName === "edit") {
      const paths = getPaths(input);
      for (const p of paths) {
        if (SENSITIVE_PATH_RE.test(p)) {
          audit(cwd, "tool_blocked", toolName + ": " + p, "SENSITIVE_PATH");
          return {
            block: true,
            reason: "[vibekit 安全] 禁止写入敏感文件: " + p +
              "（密钥/凭据/私钥）。密钥只存 ~/.pi/agent/auth.json。",
          };
        }
      }
      if (paths.length > 0) {
        audit(cwd, "tool_call", toolName + ": " + paths.join(",").slice(0, 100), "ok");
      }
    }
  });
}
