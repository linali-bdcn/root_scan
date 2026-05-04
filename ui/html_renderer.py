import os
import datetime
import plotly.graph_objects as go
import plotly.express as px
from utils.formatters import format_size
from config.settings import HISTORY_DIR, CHART_COLORWAY, THEME_BG_COLOR, THEME_PANEL_BG



# 🌟 关键优化 1：引入 current_depth 和 export_max_depth 进行物理剪枝
def _build_plotly_data(node, parent_path, ids, labels, parents, values, texts, customdata, current_depth,
                       export_max_depth):
    current_id = node["path"]
    ids.append(current_id)
    labels.append(node["name"])
    parents.append(parent_path)
    values.append(node["size"])
    texts.append(format_size(node["size"]))

    if node["type"] == "dir":
        t_str = "📁 文件夹"
    elif node["type"] == "file":
        t_str = "📄 单个文件"
    else:
        t_str = "🧩 碎片文件集合"

    customdata.append([current_id, t_str])

    # 🌟 核心防卡死机制：如果当前层级已经达到出口极限，立刻停止生成更深层的数据！
    if current_depth >= export_max_depth:
        return

    for child in node["children"]:
        _build_plotly_data(child, current_id, ids, labels, parents, values, texts, customdata, current_depth + 1,
                           export_max_depth)


def generate_ui(tree_data, target_drive, max_depth=3, is_temp=False):
    if is_temp:
        filename = "temp_linked_view.html"
    else:
        safe_drive = target_drive.replace(":\\", "").replace("/", "_")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Scan_{safe_drive}_{timestamp}.html"

    filepath = os.path.join(HISTORY_DIR, filename)

    ids, labels, parents, values, texts, customdata = [], [], [], [], [], []

    # 🌟 关键优化 2：为了保证点击图表时还能往下看两层，我们把实际导出的数据层级设为 max_depth + 2
    # 这样既保证了交互性，又把 HTML 的体积缩小了 90% 以上！
    export_max_depth = max_depth + 2
    _build_plotly_data(tree_data, "", ids, labels, parents, values, texts, customdata, current_depth=1,
                       export_max_depth=export_max_depth)

    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values,
        textinfo="label+text", text=texts, customdata=customdata,
        hovertemplate=(
            "<b style='font-size: 16px'>%{label}</b><br><br>"
            "📦 <b>大小:</b> %{text}<br>"
            "📊 <b>父级占比:</b> %{percentParent:.1%}<br>"
            "📌 <b>类型:</b> %{customdata[1]}<br>"
            "🔗 <b>路径:</b> %{customdata[0]}<br><extra></extra>"
        ),
        branchvalues="total",
        maxdepth=max_depth,
        marker=dict(line=dict(width=1.5, color=THEME_BG_COLOR)),  # 让图表边线和背景融为一体
        tiling=dict(pad=3),
        pathbar=dict(visible=True, thickness=35, textfont=dict(size=14))
    ))

    fig.update_layout(
        title=dict(text=f"💽 分析报告 - [{tree_data['path']}]  总容量: {format_size(tree_data['size'])}",
                   font=dict(size=20)),
        margin=dict(t=60, l=15, r=15, b=15),
        treemapcolorway=CHART_COLORWAY,
        template="plotly_dark",
        paper_bgcolor=THEME_PANEL_BG,
        plot_bgcolor=THEME_PANEL_BG,
        font=dict(color="#E0E0E0")
    )

    fig.write_html(filepath, auto_open=False)

    # 注入 CSS 让网页周边无缝变暗
    with open(filepath, 'r', encoding='utf-8') as f:
        html_content = f.read()
    dark_css = f"""
    <style>
        body, html {{ 
            background-color: {THEME_PANEL_BG} !important; 
            margin: 0; padding: 0; overflow: hidden; 
        }}
    </style>
    </head>
    """
    html_content = html_content.replace("</head>", dark_css)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return os.path.abspath(filepath)