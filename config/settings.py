import os

# ==========================================
# 1. 核心扫描配置
# ==========================================
SIZE_THRESHOLD_MB = 50
SIZE_THRESHOLD_BYTES = SIZE_THRESHOLD_MB * 1024 * 1024
DEFAULT_RENDER_DEPTH = 3

IGNORE_DIRS = {
    '$RECYCLE.BIN',
    'System Volume Information',
    '.git',
    'node_modules',
    'Windows'
}

OUTPUT_DIR = "output"
HISTORY_DIR = os.path.join(OUTPUT_DIR, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)

# ==========================================
# 2. 全局主题引擎 (修复透明BUG，采用实色质感深色)
# ==========================================

# 全局主题库 (抛弃 rgba，使用纯净的 HEX 颜色保证极致性能和颜值)
THEMES = {
    "Slate": { # 高级灰系
        "bg": "#1E1E1E", "panel": "#252526",
        "border": "#3E3E42", "accent": "#007ACC", "hover": "#1F8AD2",
        "chart": ["#4a5568", "#2d3748", "#718096", "#a0aec0"]
    },
    "Ocean": { # 纯净深海蓝
        "bg": "#0B1120", "panel": "#111827",
        "border": "#1E3A8A", "accent": "#2563EB", "hover": "#3B82F6",
        "chart": ["#1e3a8a", "#1d4ed8", "#3b82f6", "#93c5fd"]
    },
    "Sunset": { # 温暖日落橘
        "bg": "#2A130B", "panel": "#1E0D08",
        "border": "#9A3412", "accent": "#EA580C", "hover": "#F97316",
        "chart": ["#7c2d12", "#b45309", "#d97706", "#fcd34d"]
    },
    "Neon": { # 赛博朋克紫
        "bg": "#1A1025", "panel": "#130A1C",
        "border": "#6D28D9", "accent": "#8B5CF6", "hover": "#A78BFA",
        "chart": ["#ef4444", "#f97316", "#10b981", "#3b82f6", "#8b5cf6"]
    }
}
# 🌟 在这里填入你想使用的全局色系名称 (Slate / Ocean / Sunset / Neon)
ACTIVE_THEME = "Slate"

THEME_BG_COLOR = THEMES[ACTIVE_THEME]["bg"]
THEME_PANEL_BG = THEMES[ACTIVE_THEME]["panel"]
THEME_BORDER = THEMES[ACTIVE_THEME]["border"]
THEME_ACCENT = THEMES[ACTIVE_THEME]["accent"]
THEME_ACCENT_HOVER = THEMES[ACTIVE_THEME]["hover"]
CHART_COLORWAY = THEMES[ACTIVE_THEME]["chart"]

THEME_TEXT_COLOR = "#E0E0E0"
THEME_WARNING = "#FF6B6B"