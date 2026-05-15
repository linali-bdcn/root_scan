const API_BASE = window.location.origin;
let globalTreeRoot = null;
let currentRenderNode = null;
let currentJobId = null;
let jobPollingInterval = null;
let currentExportJSON = null;
let matchedListNodes = [];

// ================= 主题与格式化 =================
const THEME_PALETTES = {
    "Slate": { bg: "#1E1E1E", panel: "#252526", border: "#3E3E42", accent: "#007ACC", hover: "#1F8AD2", chart: ["#4a5568", "#2d3748", "#718096", "#a0aec0"] },
    "Ocean": { bg: "#0B1120", panel: "#111827", border: "#1E3A8A", accent: "#2563EB", hover: "#3B82F6", chart: ["#1e3a8a", "#1d4ed8", "#3b82f6", "#93c5fd"] },
    "Sunset": { bg: "#2A130B", panel: "#1E0D08", border: "#9A3412", accent: "#EA580C", hover: "#F97316", chart: ["#7c2d12", "#b45309", "#d97706", "#fcd34d"] },
    "Neon": { bg: "#1A1025", panel: "#130A1C", border: "#6D28D9", accent: "#8B5CF6", hover: "#A78BFA", chart: ["#ef4444", "#f97316", "#10b981", "#3b82f6", "#8b5cf6"] }
};

function applyTheme(themeName) {
    const p = THEME_PALETTES[themeName]; if (!p) return;
    document.documentElement.style.setProperty('--bg-color', p.bg); document.documentElement.style.setProperty('--panel-bg', p.panel);
    document.documentElement.style.setProperty('--border-color', p.border); document.documentElement.style.setProperty('--accent-color', p.accent);
    document.documentElement.style.setProperty('--hover-color', p.hover);
    localStorage.setItem('userTheme', themeName);
    if (currentRenderNode) renderPlotly(currentRenderNode);
}

document.getElementById('themeSelect').onchange = (e) => applyTheme(e.target.value);
document.getElementById('exportPathInput').onchange = (e) => localStorage.setItem('exportPath', e.target.value);

function formatSize(bytes) {
    if (bytes === 0) return '0 B'; const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// ================= 严格的树结构状态机 =================
function initNodeState(node, parentNode) {
    if (!node) return;
    node.parent = parentNode; node.checked = false; node.fullSelected = false;
    node.checkboxEl = null; node.rowEl = null; node.toggleBtnEl = null;
    if (node.children) node.children.forEach(child => initNodeState(child, node));
}

function updateCheckboxUI(node) {
    const cb = node.checkboxEl; if (!cb) return;
    cb.className = 'checkbox-custom'; cb.textContent = '';
    if (node.checked) {
        if (node.type === 'dir' && !node.fullSelected && node.children && node.children.some(c => c.checked)) cb.classList.add('indeterminate');
        else { cb.classList.add('checked'); cb.textContent = '✓'; }
    }
}

function setCheckedRecursive(node, checked) {
    node.checked = checked; node.fullSelected = checked; updateCheckboxUI(node);
    if (node.children) node.children.forEach(child => setCheckedRecursive(child, checked));
}

function updateParentState(parent) {
    if (!parent.children || parent.children.length === 0) return;
    const allFilesAndDirsChecked = parent.children.every(c => {
        if (c.type === 'file' || c.type === 'others') return c.checked;
        return c.checked && c.fullSelected;
    });
    const anyChecked = parent.children.some(c => c.checked);

    if (allFilesAndDirsChecked) { parent.checked = true; parent.fullSelected = true; }
    else if (anyChecked) { parent.checked = true; parent.fullSelected = false; }
    else { parent.checked = false; parent.fullSelected = false; }
    updateCheckboxUI(parent);
}

function propagateUp(node) { let p = node.parent; while (p) { updateParentState(p); p = p.parent; } }

function recalculateEntireTree(node) {
    if (!node.children || node.children.length === 0) {
        updateCheckboxUI(node); return;
    }
    node.children.forEach(recalculateEntireTree);

    const allFull = node.children.every(c => (c.type === 'file' || c.type === 'others') ? c.checked : (c.checked && c.fullSelected));
    const anyCheck = node.children.some(c => c.checked);

    if (allFull && node.children.length > 0) { node.checked = true; node.fullSelected = true; }
    else if (anyCheck) { node.checked = true; node.fullSelected = false; }
    else { node.checked = false; node.fullSelected = false; }

    updateCheckboxUI(node);
}

function updateSelectionSize() {
    let count = 0; let totalBytes = 0;
    function calc(n) {
        if (!n) return;
        if ((n.type === 'file' || n.type === 'others') && n.checked && n.type !== 'others') { count++; totalBytes += n.size; }
        else if (n.type === 'dir' && n.checked && n.fullSelected) { count++; totalBytes += n.size; }
        else if (n.type === 'dir' && n.checked && !n.fullSelected && n.children) { n.children.forEach(calc); }
    }
    if (globalTreeRoot) calc(globalTreeRoot);

    document.getElementById('selectCount').innerText = count > 0 ? `已选中 ${count} 项` : '未选择';
    document.getElementById('selectSize').innerText = count > 0 ? formatSize(totalBytes) : '0 B';

    const actionPanel = document.getElementById('batchActions');
    actionPanel.style.opacity = count > 0 ? '1' : '0.5';
    actionPanel.style.pointerEvents = count > 0 ? 'auto' : 'none';
    return totalBytes;
}

function toggleNodeCheck(node) {
    setCheckedRecursive(node, !node.checked);
    propagateUp(node);
    updateSelectionSize();
}

function setActiveRow(rowEl, node) {
    document.querySelectorAll('.node-row').forEach(r => r.classList.remove('active'));
    rowEl.classList.add('active');
    rowEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderTree(node, container) {
    const row = document.createElement('div'); row.className = 'node-row'; node.rowEl = row;
    const toggleBtn = document.createElement('span'); toggleBtn.className = 'toggle-btn'; node.toggleBtnEl = toggleBtn;
    const checkBox = document.createElement('div'); node.checkboxEl = checkBox; updateCheckboxUI(node);

    const nameSpan = document.createElement('span'); nameSpan.className = 'node-name'; nameSpan.textContent = node.name;
    const sizeSpan = document.createElement('span'); sizeSpan.className = 'node-size'; sizeSpan.textContent = formatSize(node.size);
    const childrenContainer = document.createElement('div'); childrenContainer.className = 'children-ul';

    let isRendered = false;
    node.expandLogic = () => {
        if (!node.children || node.children.length === 0) return;
        toggleBtn.classList.toggle('expanded'); childrenContainer.classList.toggle('expanded');
        if (!isRendered) { node.children.forEach(child => renderTree(child, childrenContainer)); isRendered = true; }
    };

    if (node.children && node.children.length > 0) {
        toggleBtn.innerHTML = '▶';
        toggleBtn.onclick = (e) => { e.stopPropagation(); node.expandLogic(); setActiveRow(row, node); };
    } else toggleBtn.classList.add('placeholder');

    checkBox.onclick = (e) => { e.stopPropagation(); toggleNodeCheck(node); setActiveRow(row, node); };

    row.onclick = (e) => {
        if (e.ctrlKey) { fetch(`${API_BASE}/api/action/open?path=${encodeURIComponent(node.path)}`); return; }
        setActiveRow(row, node); renderPlotly(node); if (node.expandLogic) node.expandLogic();
    };

    row.oncontextmenu = (e) => {
        if (e.ctrlKey) { e.preventDefault(); toggleNodeCheck(node); setActiveRow(row, node); }
    };

    row.append(toggleBtn, checkBox, nameSpan, sizeSpan);
    container.append(row, childrenContainer);
}


// ================= 🌟 完美修复：Plotly 图表引擎 (手动精算百分比) =================
function buildPlotlyData(nodeData, maxDepth) {
    let ids = [], labels = [], parents = [], values = [], texts = [], customdata = [];

    // 递归时传入父级的体积 parentSize
    function flatten(n, parentPath, currentDepth, parentSize) {
        let currentId = n.path;
        ids.push(currentId);
        labels.push(n.name);
        parents.push(parentPath);
        values.push(n.size);
        texts.push(formatSize(n.size));

        // 🌟 核心：在此处用最高精度计算百分比，绕开 Plotly 的内部折叠运算 BUG！
        let percentStr = "100.00%"; // 根节点是 100%
        if (parentSize && parentSize > 0) {
            percentStr = ((n.size / parentSize) * 100).toFixed(2) + "%";
        }

        // 存入 customdata 的第3个位置 (索引2)
        customdata.push([currentId, n.type === 'dir' ? '📁' : '📄', percentStr]);

        if (n.children && currentDepth < maxDepth + 1) {
            n.children.forEach(child => flatten(child, currentId, currentDepth + 1, n.size));
        }
    }

    flatten(nodeData, "", 0, null);
    return { ids, labels, parents, values, texts, customdata };
}

function renderPlotly(nodeData) {
    currentRenderNode = nodeData; const depth = parseInt(document.getElementById('renderDepth').value) || 3;
    const pData = buildPlotlyData(nodeData, depth); const palette = THEME_PALETTES[localStorage.getItem('userTheme') || 'Ocean'];

    Plotly.newPlot('plotly-view', [{
        type: 'treemap', ids: pData.ids, labels: pData.labels, parents: pData.parents,
        values: pData.values, text: pData.texts, textinfo: 'label+text', branchvalues: 'remainder',
        customdata: pData.customdata,
        // 🌟 将原本罢工的 %{percentParent} 替换为我们自己精准计算的 %{customdata[2]}
        hovertemplate: "<b style='font-size: 16px'>%{label}</b><br><br>📦 <b>大小:</b> %{text}<br>📊 <b>父级占比:</b> %{customdata[2]}<br>📌 <b>类型:</b> %{customdata[1]}<br>🔗 <b>路径:</b> %{customdata[0]}<br><extra></extra>",
        maxdepth: depth, marker: { line: { width: 1.5, color: palette.panel } }, tiling: { pad: 3 }, pathbar: { visible: true, thickness: 35 }
    }], { margin: { t: 30, l: 10, r: 10, b: 10 }, paper_bgcolor: palette.bg, plot_bgcolor: palette.bg, font: { color: '#E0E0E0' }, treemapcolorway: palette.chart }, {responsive: true});
}

// ================= 键盘拦截引擎 =================
document.addEventListener('keydown', (e) => {
    const activeRow = document.querySelector('.node-row.active'); if (!activeRow) return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    const visibleRows = Array.from(document.querySelectorAll('.node-row')).filter(r => r.offsetParent !== null);
    const idx = visibleRows.indexOf(activeRow);

    if (e.key === 'ArrowDown') { e.preventDefault(); if (idx < visibleRows.length - 1) visibleRows[idx + 1].click(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); if (idx > 0) visibleRows[idx - 1].click(); }
    else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault(); const tb = activeRow.querySelector('.toggle-btn');
        if (tb && !tb.classList.contains('placeholder')) {
            const isExp = tb.classList.contains('expanded');
            if ((e.key === 'ArrowRight' && !isExp) || (e.key === 'ArrowLeft' && isExp)) tb.click();
        }
    }
    else if (e.key === ' ') { e.preventDefault(); activeRow.querySelector('.checkbox-custom').click(); }
    else if (e.key === 'Enter') { e.preventDefault(); activeRow.click(); }
});

// ================= 高级匹配与同步勾选引擎 =================
document.getElementById('btnFilterStats').onclick = () => document.getElementById('modalFilter').style.display = 'flex';

document.getElementById('btnRunMatch').onclick = () => {
    if (!globalTreeRoot) return alert("请先进行磁盘扫描！");

    const useName = document.getElementById('cbRuleName').checked;
    const valName = document.getElementById('ruleName').value.toLowerCase();

    const useRegex = document.getElementById('cbRuleRegex').checked;
    const valRegex = document.getElementById('ruleRegex').value;
    let regexObj = null;
    if (useRegex && valRegex) { try { regexObj = new RegExp(valRegex, 'i'); } catch(e){ return alert("正则表达式语法错误！"); } }

    const useExt = document.getElementById('cbRuleExt').checked;
    let exts = [];
    if (useExt) { exts = document.getElementById('ruleExt').value.split(',').map(s => s.trim().toLowerCase().replace('.', '')).filter(s => s); }

    const useSize = document.getElementById('cbRuleSize').checked;
    const minBytes = (parseFloat(document.getElementById('ruleMinSize').value) || 0) * 1024 * 1024;
    const maxBytes = (parseFloat(document.getElementById('ruleMaxSize').value) || 9999999) * 1024 * 1024;

    matchedListNodes = [];
    const container = document.getElementById('matchListContainer'); container.innerHTML = '';

    function searchMatch(node) {
        let pass = true;
        if (useName && !node.name.toLowerCase().includes(valName)) pass = false;
        if (pass && useRegex && regexObj && !regexObj.test(node.name)) pass = false;
        if (pass && useSize && (node.size < minBytes || node.size > maxBytes)) pass = false;
        if (pass && useExt) {
            if (node.type !== 'file') pass = false;
            else {
                const ext = node.name.includes('.') ? node.name.split('.').pop().toLowerCase() : '';
                if (!exts.includes(ext)) pass = false;
            }
        }

        if (pass && node.type !== 'others') matchedListNodes.push(node);
        if (node.children) node.children.forEach(searchMatch);
    }

    searchMatch(globalTreeRoot);
    document.getElementById('matchListCount').innerText = `共匹配到 ${matchedListNodes.length} 项`;

    if (matchedListNodes.length === 0) {
        container.innerHTML = '<div style="text-align:center; color:var(--text-muted); margin-top:30px;">无符合条件的文件。 (提示：如果找小文件，请先将侧边栏过滤阈值设为 0 重扫)</div>';
        return;
    }

    matchedListNodes.forEach(node => {
        node.listChecked = true;
        const itemDiv = document.createElement('div'); itemDiv.className = 'match-item';
        const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = true;
        cb.onclick = (e) => { node.listChecked = e.target.checked; };

        const pathSpan = document.createElement('span'); pathSpan.className = 'match-path';
        pathSpan.textContent = node.path + (node.type === 'dir' ? ' (目录)' : ''); pathSpan.title = node.path;
        const sizeSpan = document.createElement('span'); sizeSpan.className = 'match-size'; sizeSpan.textContent = formatSize(node.size);

        itemDiv.append(cb, pathSpan, sizeSpan); container.appendChild(itemDiv);
    });
};

document.getElementById('cbListSelectAll').onchange = (e) => {
    const isChecked = e.target.checked;
    const checkboxes = document.getElementById('matchListContainer').querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = isChecked);
    matchedListNodes.forEach(n => n.listChecked = isChecked);
};

document.getElementById('btnSyncToMain').onclick = () => {
    if (matchedListNodes.length === 0) return alert("当前列表没有匹配项");

    let syncCount = 0;
    matchedListNodes.forEach(node => {
        if (node.listChecked && !node.checked) {
            node.checked = true; syncCount++;
        }
    });

    if (syncCount > 0) {
        recalculateEntireTree(globalTreeRoot);
        updateSelectionSize();
        alert(`✅ 同步完成！已将 ${syncCount} 个文件状态完美同步至主视图。`);
    } else {
        alert("没有需要新同步的选项。");
    }
};


document.getElementById('btnCalcStats').onclick = () => {
    if (!globalTreeRoot) return;
    const targetMode = document.getElementById('statsTarget').value;
    const optCount = document.getElementById('statOptCount').checked;
    const optAvg = document.getElementById('statOptAvg').checked;
    const optTop = document.getElementById('statOptTopExt').checked;

    let count = 0; let totalSize = 0; let extMap = {};

    function addStat(n) {
        count++; totalSize += n.size;
        const ext = n.name.includes('.') ? n.name.split('.').pop().toLowerCase() : '无扩展名';
        if(!extMap[ext]) extMap[ext] = { count: 0, size: 0 };
        extMap[ext].count++; extMap[ext].size += n.size;
    }

    if (targetMode === 'list_checked') {
        matchedListNodes.forEach(n => { if (n.listChecked && n.type === 'file') addStat(n); });
    } else if (targetMode === 'main_selected') {
        function traverseMain(n) {
            if ((n.type === 'file' || n.type === 'others') && n.checked) addStat(n);
            else if (n.type === 'dir' && n.checked && n.fullSelected) {
                function countAll(child) {
                    if (child.type === 'file' || child.type === 'others') addStat(child);
                    if (child.children) child.children.forEach(countAll);
                }
                if (n.children) n.children.forEach(countAll);
            }
            else if (n.type === 'dir' && n.checked && !n.fullSelected) {
                if (n.children) n.children.forEach(traverseMain);
            }
        }
        traverseMain(globalTreeRoot);
    } else if (targetMode === 'all') {
        function traverseAll(n) {
            if (n.type === 'file' || n.type === 'others') addStat(n);
            if (n.children) n.children.forEach(traverseAll);
        }
        traverseAll(globalTreeRoot);
    }

    if (count === 0) return document.getElementById('statsResult').innerText = "❌ 目标范围内没有找到文件。(若是文件夹被全选，请确保内部有具体文件)";

    let report = `📊 统计报告生成于: ${new Date().toLocaleTimeString()}\n----------------------------------------\n`;
    if (optCount) report += `总计文件数量: ${count} 个\n总计占用空间: ${formatSize(totalSize)}\n\n`;
    if (optAvg) report += `平均单文件大小: ${formatSize(totalSize/count)}\n\n`;

    if (optTop) {
        report += `📂 扩展名空间占比 TOP 10:\n`;
        let extList = Object.keys(extMap).map(k => ({ ext: k, count: extMap[k].count, size: extMap[k].size }));
        extList.sort((a,b) => b.size - a.size);
        extList.slice(0, 10).forEach(item => {
            const pct = ((item.size / totalSize) * 100).toFixed(2);
            report += `  [.${item.ext}] -> ${item.count}个 | ${formatSize(item.size)} (${pct}%)\n`;
        });
    }
    document.getElementById('statsResult').innerText = report;
};


// ================= 异步任务 API =================
function getSelectedPaths() {
    let paths = [];
    function collect(node) {
        if ((node.type === 'file' || node.type === 'others') && node.checked && node.type !== 'others') paths.push(node.path);
        else if (node.type === 'dir' && node.checked && node.fullSelected) paths.push(node.path);
        else if (node.type === 'dir' && node.checked && !node.fullSelected && node.children) node.children.forEach(collect);
    }
    collect(globalTreeRoot); return paths;
}

async function startJob(action, targetPath = "") {
    const paths = getSelectedPaths(); const totalBytes = updateSelectionSize();
    if (paths.length === 0) return alert("未选择有效文件");

    if (action === 'delete') {
        if (totalBytes > 1024*1024*1024) {
            if(!confirm("⚠️ 警告 1: 您即将删除超过 1GB 的数据！继续吗？")) return;
            if(!confirm("⚠️ 警告 2: 该操作不经过回收站，将被彻底物理删除！确认？")) return;
            if(!confirm("⚠️ 警告 3: 最终确认。如果发生误删，请保留 logs/ 目录日志！")) return;
        } else {
            if(!confirm(`确认彻底物理删除 ${paths.length} 项数据吗？\n(总体积: ${formatSize(totalBytes)})`)) return;
        }
    }

    document.getElementById('modalInput').style.display = 'none'; document.getElementById('modalProgress').style.display = 'flex';
    document.getElementById('progressTitle').innerText = `${action.toUpperCase()} 执行中...`;

    try {
        const res = await fetch(API_BASE + "/api/jobs/start", { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ action: action, paths: paths, target: targetPath, total_bytes: totalBytes }) });
        const data = await res.json(); currentJobId = data.job_id; jobPollingInterval = setInterval(pollJobStatus, 500);
    } catch (e) { alert("任务启动失败"); document.getElementById('modalProgress').style.display = 'none'; }
}

async function pollJobStatus() {
    if(!currentJobId) return;
    try {
        const res = await fetch(`${API_BASE}/api/jobs/status?job_id=${currentJobId}`); const job = await res.json();
        document.getElementById('progressFill').style.width = job.progress + "%";
        document.getElementById('progressText').innerText = `进度: ${job.progress}% | 成功: ${job.success} | 失败: ${job.failed}\n当前处理: ${job.current_file}`;

        if (job.status === 'completed' || job.status === 'error' || job.status === 'cancelled') {
            clearInterval(jobPollingInterval);
            let msg = `任务已停止 [${job.status}]\n成功: ${job.success}, 失败: ${job.failed}`;
            if (job.error) msg += `\n错误原因: ${job.error}`;
            alert(msg); document.getElementById('modalProgress').style.display = 'none'; document.getElementById('scanBtn').click();
        }
    } catch(e) {}
}

document.getElementById('btnCancelJob').onclick = () => {
    if(currentJobId && confirm("⚠️ 确定要紧急停止吗？可能会产生不完整文件！")) {
        fetch(`${API_BASE}/api/jobs/cancel?job_id=${currentJobId}`, {method: 'POST'});
        document.getElementById('btnCancelJob').innerText = "正在发送中止信号...";
    }
};

document.getElementById('btnDelete').onclick = () => startJob('delete');
document.getElementById('btnCompress').onclick = () => { document.getElementById('modalInputTitle').innerText = "📦 输入生成的 zip 绝对路径"; document.getElementById('modalInputVal').placeholder = "D:\\Backup.zip"; document.getElementById('modalInput').style.display = 'flex'; document.getElementById('modalInputConfirm').onclick = () => startJob('compress', document.getElementById('modalInputVal').value); };
document.getElementById('btnMove').onclick = () => { document.getElementById('modalInputTitle').innerText = "🚚 输入转移文件夹绝对路径"; document.getElementById('modalInputVal').placeholder = "E:\\MovedFiles"; document.getElementById('modalInput').style.display = 'flex'; document.getElementById('modalInputConfirm').onclick = () => startJob('move', document.getElementById('modalInputVal').value); };

// ================= 高级保存导出 =================
document.getElementById('btnExport').onclick = () => {
    if (!globalTreeRoot) return;
    let selectedDetails = []; let totalSize = 0;
    function collectDetails(node) {
        if ((node.type === 'file' || node.type === 'others') && node.checked && node.type !== 'others') { selectedDetails.push({ path: node.path, sizeBytes: node.size, type: node.type }); totalSize += node.size; }
        else if (node.type === 'dir' && node.checked && node.fullSelected) { selectedDetails.push({ path: node.path, sizeBytes: node.size, type: node.type }); totalSize += node.size; }
        else if (node.type === 'dir' && node.checked && !node.fullSelected) { if (node.children) node.children.forEach(collectDetails); }
    }
    collectDetails(globalTreeRoot);

    currentExportJSON = { metadata: { exportTime: new Date().toLocaleString(), totalSelected: selectedDetails.length, totalSizeAllocated: formatSize(totalSize) }, items: selectedDetails };
    document.getElementById('modalTextTitle').innerText = "📄 高级选定清单 (JSON)";
    document.getElementById('modalTextPre').textContent = JSON.stringify(currentExportJSON, null, 2);
    document.getElementById('modalText').style.display = 'flex';
};

document.getElementById('btnSaveLocal').onclick = async () => {
    const defaultDir = localStorage.getItem('exportPath') || 'D:\\SpaceAnalyzer_Exports';
    const timestamp = new Date().toISOString().replace(/[:\.]/g, '-');
    const targetFile = `${defaultDir}\\Export_${timestamp}.json`;
    try {
        const res = await fetch(`${API_BASE}/api/action/export`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ target: targetFile, data: currentExportJSON }) });
        const result = await res.json(); if (!res.ok) throw new Error(result.detail); alert(result.message);
    } catch (e) { alert("保存失败: " + e.message); }
};

// ================= 初始化 =================
window.onload = async () => {
    const savedTheme = localStorage.getItem('userTheme') || 'Ocean'; document.getElementById('themeSelect').value = savedTheme; applyTheme(savedTheme);
    const savedPath = localStorage.getItem('exportPath') || ''; if (savedPath) document.getElementById('exportPathInput').value = savedPath;
    const res = await fetch(`${API_BASE}/api/drives`); const drives = await res.json(); const select = document.getElementById('driveSelect');
    drives.forEach(d => { const opt = document.createElement('option'); opt.value = d; opt.textContent = d; select.appendChild(opt); });
};

document.getElementById('scanBtn').onclick = async () => {
    const target = document.getElementById('driveSelect').value;
    const thresholdMb = document.getElementById('scanThreshold').value || 0;

    document.getElementById('loadingOverlay').style.display = 'flex';
    document.getElementById('loadingOverlay').innerText = `🚀 正在深度扫描 ${target} (阈值:${thresholdMb}MB)...`;
    document.getElementById('treeContainer').innerHTML = '';

    globalTreeRoot = null; matchedListNodes = []; updateSelectionSize();

    try {
        const res = await fetch(`${API_BASE}/api/scan?target=${encodeURIComponent(target)}&threshold_mb=${thresholdMb}`);
        if (!res.ok) { let err = await res.text(); try { err = JSON.parse(err).detail; } catch(e){} throw new Error(err); }

        const treeData = await res.json();
        initNodeState(treeData, null); globalTreeRoot = treeData;

        document.getElementById('statusText').innerText = "✅ 扫描完成";
        renderTree(treeData, document.getElementById('treeContainer'));
        renderPlotly(treeData);

        const firstRow = document.querySelector('.node-row');
        if (firstRow) setActiveRow(firstRow, treeData);
    } catch (err) { alert("扫描出错：" + err.message); }
    finally { document.getElementById('loadingOverlay').style.display = 'none'; }
};