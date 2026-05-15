import os
import sys
import string
import uvicorn
import webbrowser
import threading
import shutil
import zipfile
import subprocess
import json
import uuid
import time
import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict

IGNORE_DIRS = {'$RECYCLE.BIN', 'System Volume Information', '.git', 'node_modules', 'Windows'}

app = FastAPI(title="Disk Space Analyzer Pro API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# ================= 异步任务与日志引擎 =================
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)


class JobReq(BaseModel):
    action: str  # 'delete', 'move', 'compress'
    paths: List[str]
    target: str = ""
    total_bytes: int = 0


jobs_db: Dict[str, dict] = {}


def get_free_space(path):
    """获取指定路径所在的磁盘剩余空间"""
    try:
        return shutil.disk_usage(os.path.abspath(path)).free
    except:
        return float('inf')


def write_log(job_id, action, status, details):
    log_file = os.path.join(LOG_DIR, f"op_{datetime.datetime.now().strftime('%Y%m%d')}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().isoformat()}] [Job:{job_id}] [{action.upper()}] [{status}] {details}\n")


def background_job_runner(job_id: str, req: JobReq):
    job = jobs_db[job_id]
    write_log(job_id, req.action, "START", f"Paths: {len(req.paths)}, Target: {req.target}")

    # 1. 预判空间容量 (转移和压缩)
    if req.action in ['move', 'compress']:
        target_dir = os.path.dirname(req.target) if req.action == 'compress' else req.target
        if target_dir and os.path.exists(target_dir):
            free_space = get_free_space(target_dir)
            if req.total_bytes > free_space:
                job['status'] = 'error'
                job[
                    'error'] = f"空间不足！需要: {req.total_bytes / 1024 ** 3:.2f}GB, 剩余: {free_space / 1024 ** 3:.2f}GB"
                write_log(job_id, req.action, "FAILED", job['error'])
                return

    total = len(req.paths)
    manifest_data = []

    try:
        if req.action == 'compress':
            target_zip = req.target if req.target.endswith(".zip") else req.target + ".zip"
            os.makedirs(os.path.dirname(target_zip), exist_ok=True)
            with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for i, p in enumerate(req.paths):
                    if job.get('cancel'): break
                    job['current_file'] = p
                    try:
                        if os.path.isfile(p):
                            arc = os.path.basename(p)
                            zipf.write(p, arc)
                            manifest_data.append(f"{arc} <- {p}")
                        elif os.path.isdir(p):
                            for root, _, files in os.walk(p):
                                for file in files:
                                    if job.get('cancel'): break
                                    file_path = os.path.join(root, file)
                                    arc = os.path.relpath(file_path, os.path.dirname(p))
                                    zipf.write(file_path, arc)
                                    manifest_data.append(f"{arc} <- {file_path}")
                        job['success'] += 1
                    except:
                        job['failed'] += 1
                    job['progress'] = int(((i + 1) / total) * 100)
                    time.sleep(0.01)  # 控制速度，防止卡死并响应取消信号

                # 压缩完毕后，写入清单文件到包内
                if not job.get('cancel'):
                    zipf.writestr("manifest_record.txt", "\n".join(manifest_data))
                    write_log(job_id, req.action, "SUCCESS", f"Compressed to {target_zip}")

        elif req.action == 'delete':
            for i, p in enumerate(req.paths):
                if job.get('cancel'): break
                job['current_file'] = p
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                    elif os.path.isdir(p):
                        shutil.rmtree(p)
                    job['success'] += 1
                    write_log(job_id, req.action, "DELETED", p)
                except:
                    job['failed'] += 1
                job['progress'] = int(((i + 1) / total) * 100)
                time.sleep(0.05)  # 刻意降速，让用户有时间紧急停止

        elif req.action == 'move':
            os.makedirs(req.target, exist_ok=True)
            for i, p in enumerate(req.paths):
                if job.get('cancel'): break
                job['current_file'] = p
                try:
                    shutil.move(p, req.target)
                    job['success'] += 1
                    write_log(job_id, req.action, "MOVED", f"{p} -> {req.target}")
                except:
                    job['failed'] += 1
                job['progress'] = int(((i + 1) / total) * 100)
                time.sleep(0.01)

        if job.get('cancel'):
            job['status'] = 'cancelled'
            write_log(job_id, req.action, "CANCELLED", "User aborted.")
        else:
            job['status'] = 'completed'
            job['progress'] = 100

    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)
        write_log(job_id, req.action, "ERROR", str(e))


@app.post("/api/jobs/start")
def start_job(req: JobReq):
    job_id = str(uuid.uuid4())
    jobs_db[job_id] = {"status": "running", "progress": 0, "success": 0, "failed": 0, "current_file": "",
                       "cancel": False, "error": None}
    threading.Thread(target=background_job_runner, args=(job_id, req), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/jobs/status")
def get_job_status(job_id: str = Query(...)):
    if job_id not in jobs_db: raise HTTPException(status_code=404)
    return jobs_db[job_id]


@app.post("/api/jobs/cancel")
def cancel_job(job_id: str = Query(...)):
    if job_id in jobs_db: jobs_db[job_id]['cancel'] = True
    return {"message": "正在终止..."}


# ================= 核心扫描算法 =================
class DiskScanner:
    def __init__(self, threshold_bytes):
        self.threshold_bytes = threshold_bytes

    def scan(self, path):
        total_size = 0;
        children = []
        name = os.path.basename(path) if os.path.basename(path) else path
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.name in IGNORE_DIRS: continue
                    try:
                        if entry.is_file(follow_symlinks=False):
                            size = entry.stat(follow_symlinks=False).st_size;
                            total_size += size
                            if size > self.threshold_bytes: children.append(
                                {"name": entry.name, "path": entry.path, "size": size, "type": "file", "children": []})
                        elif entry.is_dir(follow_symlinks=False):
                            d = self.scan(entry.path);
                            total_size += d["size"];
                            children.append(d)
                    except:
                        pass
        except:
            pass

        if total_size < self.threshold_bytes:
            children = []
        else:
            large = [];
            small_sum = 0
            for c in children:
                if c["size"] >= (self.threshold_bytes / 5):
                    large.append(c)
                else:
                    small_sum += c["size"]
            if small_sum > 0: large.append(
                {"name": "其他小文件(合并)", "path": os.path.join(path, "_others"), "size": small_sum, "type": "others",
                 "children": []})
            children = large

        children.sort(key=lambda x: x["size"], reverse=True)
        return {"name": name, "path": path.replace("\\", "/"), "size": total_size, "type": "dir", "children": children}


# ================= 基础 API =================
@app.get("/")
def serve_frontend(): return FileResponse("frontend/index.html")


@app.get("/api/drives")
def get_drives():
    drives = []
    if sys.platform == "win32":
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives();
        for letter in string.ascii_uppercase:
            if bitmask & 1: drives.append(f"{letter}:\\")
            bitmask >>= 1
    else:
        drives = ["/", os.path.expanduser("~")]
    return drives


@app.get("/api/scan")
def do_scan(target: str = Query(...), threshold_mb: int = Query(50)):
    if not os.path.exists(target): raise HTTPException(status_code=404)
    return DiskScanner(threshold_mb * 1024 * 1024).scan(target)


@app.get("/api/action/open")
def open_in_explorer(path: str = Query(...)):
    if not os.path.exists(path): raise HTTPException(status_code=404)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.call(["open", path])
    else:
        subprocess.call(["xdg-open", path])
    return {"message": "ok"}


if __name__ == "__main__":
    host, port = "127.0.0.1", 8000
    print(f"🚀 服务启动: http://{host}:{port}")
    threading.Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")