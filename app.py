"""
Pro VPS Panel - Complete with Your Templates
Owner: agajayofficialbro
"""
import os
import json
import time
import uuid
import shutil
import base64
import tarfile
import requests
import subprocess
import threading
import secrets
import mimetypes
import socket
import signal
from pathlib import Path
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from functools import wraps
import queue

app = Flask(__name__)
app.secret_key = "your-secret-key-here-change-it"

# ============ CONFIGURATION ============
GITHUB_TOKEN = "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"  # Apna token daalo
GITHUB_REPO = "bbytop62-art/vpsbackup"     # Apna repo daalo
GITHUB_BRANCH = "main"

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
FILES_ROOT = APP_DIR / "user_files"
WEBSITES_ROOT = APP_DIR / "websites"
APPS_ROOT = APP_DIR / "apps"
BACKUP_DIR = APP_DIR / "backups"

DATA_DIR.mkdir(exist_ok=True)
FILES_ROOT.mkdir(exist_ok=True)
WEBSITES_ROOT.mkdir(exist_ok=True)
APPS_ROOT.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

# ============ DEFAULT DATA ============
OWNER_USER = "admin"
OWNER_PASS = "admin123"

DEFAULT_PRICING = {
    "currency": "₹",
    "contact": "Telegram: @bbytop3",
    "plans": [
        {"name": "Starter", "duration": "24 Hours", "price": "49", "features": "1 file run, 512MB RAM"},
        {"name": "Basic", "duration": "7 Days", "price": "199", "features": "Multi-file upload, pip/npm"},
        {"name": "Pro", "duration": "30 Days", "price": "599", "features": "Unlimited modules, Priority support"},
        {"name": "Premium", "duration": "Lifetime", "price": "1999", "features": "All features, Custom domain"},
    ]
}

DEFAULT_USERS = {
    OWNER_USER: {
        "password": OWNER_PASS,
        "created_at": time.time(),
        "expires_at": time.time() + (365 * 24 * 3600),
        "token": secrets.token_urlsafe(16),
        "is_admin": True
    }
}

# ============ ASYNC TASK QUEUE ============
class TaskQueue:
    def __init__(self):
        self.queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self.is_processing = False
    
    def _worker(self):
        while True:
            try:
                task = self.queue.get(timeout=1)
                if task:
                    self.is_processing = True
                    try:
                        task()
                    except Exception as e:
                        print(f"❌ Task failed: {e}")
                    self.is_processing = False
                self.queue.task_done()
            except queue.Empty:
                time.sleep(0.1)
    
    def add_task(self, task):
        self.queue.put(task)
        return "Task queued"

task_queue = TaskQueue()

# ============ GITHUB SYNC ENGINE ============
class GitHubSync:
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.repo = GITHUB_REPO
        self.branch = GITHUB_BRANCH
        self.api_url = f"https://api.github.com/repos/{self.repo}/contents"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.is_syncing = False
        self.last_sync = 0
        self.backup_in_progress = False
        self.github_connected = False
        
    def check_github_connection(self):
        try:
            url = f"https://api.github.com/repos/{self.repo}"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                self.github_connected = True
                print("✅ GitHub connected!")
                return True
            else:
                self.github_connected = False
                return False
        except Exception as e:
            self.github_connected = False
            return False
    
    def check_if_backup_exists(self):
        try:
            url = f"{self.api_url}/data/users.json?ref={self.branch}"
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def initialize_app(self):
        print("🔄 Initializing app...")
        
        if not self.check_github_connection():
            print("⚠️ GitHub not reachable - using local data")
            self.create_default_data()
            return
        
        if not self.check_if_backup_exists():
            print("📦 No backup found - Creating default data...")
            self.create_default_data()
            self._create_initial_backup()
            return
        
        print("📥 Restoring from GitHub...")
        self._restore_from_github()
    
    def create_default_data(self):
        try:
            if (DATA_DIR / "users.json").exists():
                print("ℹ️ Local data already exists - using it")
                return
            
            print("📝 Creating default data...")
            (DATA_DIR / "users.json").write_text(json.dumps(DEFAULT_USERS, indent=2))
            (DATA_DIR / "pricing.json").write_text(json.dumps(DEFAULT_PRICING, indent=2))
            
            (FILES_ROOT / OWNER_USER).mkdir(exist_ok=True)
            (WEBSITES_ROOT / OWNER_USER).mkdir(exist_ok=True)
            (APPS_ROOT / OWNER_USER).mkdir(exist_ok=True)
            
            print("✅ Default data created!")
            print(f"👤 Admin: {OWNER_USER}")
            print(f"🔑 Password: {OWNER_PASS}")
            
        except Exception as e:
            print(f"❌ Default data creation failed: {e}")
    
    def _create_initial_backup(self):
        try:
            print("📤 Creating initial backup on GitHub...")
            
            for file in DATA_DIR.glob("*.json"):
                github_path = f"data/{file.name}"
                self._upload_file_quick(file, github_path, "Initial backup")
            
            backup_path = BACKUP_DIR / "initial_backup.tar.gz"
            with tarfile.open(backup_path, "w:gz") as tar:
                for website_dir in WEBSITES_ROOT.iterdir():
                    if website_dir.is_dir():
                        tar.add(website_dir, arcname=f"websites/{website_dir.name}")
                for app_dir in APPS_ROOT.iterdir():
                    if app_dir.is_dir():
                        tar.add(app_dir, arcname=f"apps/{app_dir.name}")
                for user_dir in FILES_ROOT.iterdir():
                    if user_dir.is_dir():
                        tar.add(user_dir, arcname=f"user_files/{user_dir.name}")
            
            self._upload_file_quick(backup_path, "backup.tar.gz", "Initial backup")
            backup_path.unlink()
            
            print("✅ Initial backup complete!")
        except Exception as e:
            print(f"❌ Initial backup failed: {e}")
    
    def _restore_from_github(self):
        try:
            print("📥 Restoring from GitHub...")
            
            files_to_restore = ["users.json", "pricing.json"]
            for filename in files_to_restore:
                local_path = DATA_DIR / filename
                github_path = f"data/{filename}"
                self._download_file_quick(github_path, local_path)
            
            backup_file = BACKUP_DIR / "temp_restore.tar.gz"
            self._download_file_quick("backup.tar.gz", backup_file)
            
            if backup_file.exists() and backup_file.stat().st_size > 0:
                with tarfile.open(backup_file, "r:gz") as tar:
                    tar.extractall(APP_DIR)
                backup_file.unlink()
                print("✅ Files restored")
            
            print("✅ Restore complete!")
        except Exception as e:
            print(f"❌ Restore failed: {e}")
            if not (DATA_DIR / "users.json").exists():
                self.create_default_data()
    
    def backup_to_github_async(self):
        if self.backup_in_progress:
            return "Backup already running"
        
        def backup_task():
            self.backup_in_progress = True
            try:
                self._backup_to_github()
            finally:
                self.backup_in_progress = False
        
        task_queue.add_task(backup_task)
        return "Backup started"
    
    def _backup_to_github(self):
        if not self.token or not self.repo:
            return False
        
        if not self.check_github_connection():
            print("⚠️ GitHub not reachable - skipping backup")
            return False
            
        try:
            print("🔄 Backing up to GitHub...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            for file in DATA_DIR.glob("*.json"):
                github_path = f"data/{file.name}"
                self._upload_file_quick(file, github_path, f"Auto backup {timestamp}")
            
            backup_path = BACKUP_DIR / f"backup.tar.gz"
            with tarfile.open(backup_path, "w:gz", compresslevel=1) as tar:
                for website_dir in WEBSITES_ROOT.iterdir():
                    if website_dir.is_dir():
                        tar.add(website_dir, arcname=f"websites/{website_dir.name}")
                for app_dir in APPS_ROOT.iterdir():
                    if app_dir.is_dir():
                        tar.add(app_dir, arcname=f"apps/{app_dir.name}")
                for user_dir in FILES_ROOT.iterdir():
                    if user_dir.is_dir():
                        tar.add(user_dir, arcname=f"user_files/{user_dir.name}")
            
            self._upload_file_quick(backup_path, "backup.tar.gz", f"Backup {timestamp}")
            backup_path.unlink()
            
            self._clean_old_backups()
            self.last_sync = time.time()
            print("✅ Backup complete!")
            return True
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False
    
    def _download_file_quick(self, github_path, local_path):
        try:
            url = f"{self.api_url}/{github_path}?ref={self.branch}"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data['content'])
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(content)
                return local_path
            return None
        except:
            return None
    
    def _upload_file_quick(self, local_path, github_path, message="Update"):
        try:
            if not local_path.exists():
                return False
            
            if local_path.suffix == '.gz' and local_path.stat().st_size < 100:
                return False
            
            with open(local_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode()
            
            url = f"{self.api_url}/{github_path}?ref={self.branch}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            data = {
                "message": message,
                "content": content,
                "branch": self.branch
            }
            
            if response.status_code == 200:
                data["sha"] = response.json()['sha']
            
            response = requests.put(
                f"{self.api_url}/{github_path}",
                headers=self.headers,
                json=data,
                timeout=30
            )
            
            return response.status_code in [200, 201]
        except:
            return False
    
    def _clean_old_backups(self):
        try:
            url = f"{self.api_url}/data?ref={self.branch}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                files = [f for f in response.json() if f['name'].startswith('backup_')]
                files.sort(key=lambda x: x['name'], reverse=True)
                
                for old_file in files[3:]:
                    delete_url = f"{self.api_url}/data/{old_file['name']}"
                    requests.delete(
                        delete_url,
                        headers=self.headers,
                        json={
                            "message": "Clean old backup",
                            "sha": old_file['sha'],
                            "branch": self.branch
                        },
                        timeout=10
                    )
        except:
            pass

# ============ INITIALIZE ============
github_sync = GitHubSync()
github_sync.initialize_app()

# Auto backup thread
def auto_backup_loop():
    while True:
        time.sleep(1800)
        github_sync.backup_to_github_async()

threading.Thread(target=auto_backup_loop, daemon=True).start()

# ============ PROCESS MANAGER ============
PROCESSES = {}
PROCESS_LOGS = {}

class ProcessManager:
    def __init__(self):
        self.processes = {}
        self.lock = threading.Lock()
    
    def start_process(self, username, app_id, app_type, port=None):
        app_dir = APPS_ROOT / username / app_id
        
        if not app_dir.exists():
            return False, "App directory not found"
        
        if not port:
            port = self.find_available_port()
        
        if not app_type:
            app_type = self.detect_app_type(app_dir)
        
        cmd = []
        env = os.environ.copy()
        env["PORT"] = str(port)
        
        if app_type == "python":
            if (app_dir / "requirements.txt").exists():
                subprocess.run(["/usr/bin/pip3", "install", "-r", str(app_dir / "requirements.txt")], 
                             cwd=str(app_dir), capture_output=True)
            
            main_file = self.find_main_file(app_dir, [".py"])
            if not main_file:
                return False, "No Python file found"
            cmd = ["/usr/bin/python3", "-u", str(main_file)]
            
        elif app_type == "node":
            if (app_dir / "package.json").exists():
                subprocess.run(["npm", "install"], cwd=str(app_dir), capture_output=True)
            
            main_file = self.find_main_file(app_dir, [".js", ".mjs"])
            if not main_file:
                return False, "No Node.js file found"
            cmd = ["node", str(main_file)]
            
        else:
            return False, f"Unsupported app type: {app_type}"
        
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(app_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                env=env,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            with self.lock:
                self.processes[f"{username}_{app_id}"] = {
                    "proc": proc,
                    "username": username,
                    "app_id": app_id,
                    "app_type": app_type,
                    "port": port,
                    "start_time": time.time(),
                    "status": "running"
                }
                PROCESS_LOGS[f"{username}_{app_id}"] = []
            
            threading.Thread(target=self._read_logs, args=(username, app_id, proc), daemon=True).start()
            
            return True, f"Started on port {port}"
            
        except Exception as e:
            return False, str(e)
    
    def stop_process(self, username, app_id):
        key = f"{username}_{app_id}"
        with self.lock:
            if key not in self.processes:
                return False, "Process not found"
            
            proc_info = self.processes[key]
            proc = proc_info["proc"]
            
            if proc.poll() is None:
                try:
                    if os.name != 'nt':
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    else:
                        proc.terminate()
                    proc.wait(timeout=5)
                except:
                    proc.kill()
            
            del self.processes[key]
            return True, "Stopped"
    
    def restart_process(self, username, app_id):
        self.stop_process(username, app_id)
        time.sleep(1)
        return self.start_process(username, app_id)
    
    def get_process_info(self, username, app_id):
        key = f"{username}_{app_id}"
        with self.lock:
            if key not in self.processes:
                return None
            proc_info = self.processes[key]
            proc = proc_info["proc"]
            return {
                "running": proc.poll() is None,
                "pid": proc.pid,
                "port": proc_info.get("port"),
                "app_type": proc_info.get("app_type"),
                "start_time": proc_info.get("start_time"),
                "uptime": time.time() - proc_info.get("start_time", 0)
            }
    
    def get_logs(self, username, app_id, lines=100):
        key = f"{username}_{app_id}"
        logs = PROCESS_LOGS.get(key, [])
        return logs[-lines:]
    
    def _read_logs(self, username, app_id, proc):
        key = f"{username}_{app_id}"
        logs = PROCESS_LOGS.get(key, [])
        
        try:
            for line in iter(proc.stdout.readline, b""):
                if not line:
                    break
                try:
                    text = line.decode("utf-8", errors="replace").strip()
                    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
                    if len(logs) > 1000:
                        logs.pop(0)
                except:
                    pass
        except:
            pass
        
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Process ended")
    
    def find_available_port(self, start=3000, end=4000):
        for port in range(start, end):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', port)) != 0:
                    return port
        return start
    
    def detect_app_type(self, app_dir):
        if any(app_dir.glob("*.py")):
            return "python"
        if any(app_dir.glob("*.js")) or (app_dir / "package.json").exists():
            return "node"
        return None
    
    def find_main_file(self, app_dir, extensions):
        common_names = ["main", "app", "index", "server", "run"]
        for name in common_names:
            for ext in extensions:
                if (app_dir / f"{name}{ext}").exists():
                    return app_dir / f"{name}{ext}"
        
        for ext in extensions:
            files = list(app_dir.glob(f"*{ext}"))
            if files:
                return files[0]
        
        return None

process_manager = ProcessManager()

# ============ USER MANAGEMENT ============
def load_users():
    if not (DATA_DIR / "users.json").exists():
        return DEFAULT_USERS
    try:
        return json.loads((DATA_DIR / "users.json").read_text())
    except:
        return DEFAULT_USERS

def save_users(users):
    (DATA_DIR / "users.json").write_text(json.dumps(users, indent=2))

def load_pricing():
    if not (DATA_DIR / "pricing.json").exists():
        return DEFAULT_PRICING
    try:
        return json.loads((DATA_DIR / "pricing.json").read_text())
    except:
        return DEFAULT_PRICING

# ============ ROUTES ============

@app.route('/')
def home():
    return render_template('landing.html', pricing=load_pricing())

@app.route('/home')
def landing():
    return render_template('landing.html', pricing=load_pricing())

@app.route('/pricing')
def pricing_page():
    return render_template('pricing.html', pricing=load_pricing())

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        
        if u == OWNER_USER and p == OWNER_PASS:
            session.clear()
            session['role'] = 'owner'
            session['username'] = u
            return redirect(url_for('owner_dashboard'))
        
        users = load_users()
        info = users.get(u)
        if info and info.get('password') == p:
            # Check expiry
            if info.get('expires_at') and time.time() > info['expires_at']:
                error = "Account expired"
            else:
                session.clear()
                session['role'] = 'user'
                session['username'] = u
                return redirect(url_for('user_dashboard'))
        else:
            error = "Invalid credentials"
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/auto/<token>')
def auto_login(token):
    users = load_users()
    for uname, info in users.items():
        if info.get('token') == token:
            if info.get('expires_at') and time.time() > info['expires_at']:
                return "Account expired", 403
            session.clear()
            session['role'] = 'user'
            session['username'] = uname
            return redirect(url_for('user_dashboard'))
    return "Invalid link", 404

# ============ OWNER ROUTES ============
@app.route('/owner')
def owner_dashboard():
    if session.get('role') != 'owner':
        return redirect(url_for('login'))
    
    users = load_users()
    now = time.time()
    base = request.host_url.rstrip('/')
    pricing = load_pricing()
    
    return render_template('owner.html', users=users, now=now, base_url=base, pricing=pricing)

@app.route('/owner/create', methods=['POST'])
def owner_create():
    if session.get('role') != 'owner':
        return redirect(url_for('login'))
    
    u = request.form.get('username', '').strip()
    p = request.form.get('password', '').strip()
    try:
        hours = float(request.form.get('hours', '24'))
    except ValueError:
        hours = 24
    
    if not u or not p or u == OWNER_USER:
        return redirect(url_for('owner_dashboard'))
    
    users = load_users()
    users[u] = {
        "password": p,
        "created_at": time.time(),
        "expires_at": time.time() + (hours * 3600) if hours > 0 else 0,
        "token": secrets.token_urlsafe(16)
    }
    save_users(users)
    (FILES_ROOT / u).mkdir(exist_ok=True)
    (WEBSITES_ROOT / u).mkdir(exist_ok=True)
    (APPS_ROOT / u).mkdir(exist_ok=True)
    
    github_sync.backup_to_github_async()
    return redirect(url_for('owner_dashboard'))

@app.route('/owner/delete/<username>', methods=['POST'])
def owner_delete(username):
    if session.get('role') != 'owner':
        return redirect(url_for('login'))
    
    users = load_users()
    if username in users:
        del users[username]
        save_users(users)
        shutil.rmtree(FILES_ROOT / username, ignore_errors=True)
        shutil.rmtree(WEBSITES_ROOT / username, ignore_errors=True)
        shutil.rmtree(APPS_ROOT / username, ignore_errors=True)
    
    github_sync.backup_to_github_async()
    return redirect(url_for('owner_dashboard'))

@app.route('/owner/extend/<username>', methods=['POST'])
def owner_extend(username):
    if session.get('role') != 'owner':
        return redirect(url_for('login'))
    
    try:
        hours = float(request.form.get('hours', '24'))
    except ValueError:
        hours = 24
    
    users = load_users()
    if username in users:
        base = max(users[username].get('expires_at') or time.time(), time.time())
        users[username]['expires_at'] = base + (hours * 3600)
        save_users(users)
    
    github_sync.backup_to_github_async()
    return redirect(url_for('owner_dashboard'))

@app.route('/owner/pricing', methods=['POST'])
def owner_pricing():
    if session.get('role') != 'owner':
        return redirect(url_for('login'))
    
    pricing = load_pricing()
    pricing['currency'] = request.form.get('currency', '₹').strip() or '₹'
    pricing['contact'] = request.form.get('contact', '').strip()
    
    plans = []
    names = request.form.getlist('p_name')
    durs = request.form.getlist('p_duration')
    prices = request.form.getlist('p_price')
    feats = request.form.getlist('p_features')
    
    for i in range(len(names)):
        if not names[i].strip():
            continue
        plans.append({
            "name": names[i].strip(),
            "duration": durs[i].strip() if i < len(durs) else "",
            "price": prices[i].strip() if i < len(prices) else "0",
            "features": feats[i].strip() if i < len(feats) else "",
        })
    
    pricing['plans'] = plans
    save_users({**load_users(), 'pricing': pricing})  # Save pricing in users file
    (DATA_DIR / "pricing.json").write_text(json.dumps(pricing, indent=2))
    
    github_sync.backup_to_github_async()
    return redirect(url_for('owner_dashboard') + '#pricing')

# ============ USER DASHBOARD ============
@app.route('/dashboard')
def user_dashboard():
    u = session.get('username')
    role = session.get('role')
    
    if not u:
        return redirect(url_for('login'))
    
    if role == 'owner':
        return redirect(url_for('owner_dashboard'))
    
    users = load_users()
    info = users.get(u, {})
    udir = FILES_ROOT / u
    files = sorted([f.name for f in udir.iterdir() if f.is_file()])
    
    return render_template('user.html',
        username=u,
        info=info,
        files=files,
        running=False,  # Will be updated via JS
        running_file=None,
        expires_at=info.get('expires_at', 0),
        now=time.time()
    )

@app.route('/upload', methods=['POST'])
def upload():
    u = session.get('username')
    if not u:
        return redirect(url_for('login'))
    
    udir = FILES_ROOT / u
    files = request.files.getlist('files')
    
    for f in files:
        if not f or not f.filename:
            continue
        name = secure_filename(f.filename)
        if not name:
            continue
        f.save(udir / name)
    
    github_sync.backup_to_github_async()
    return redirect(url_for('user_dashboard'))

@app.route('/file/delete/<name>', methods=['POST'])
def file_delete(name):
    u = session.get('username')
    if not u:
        return redirect(url_for('login'))
    
    name = secure_filename(name)
    p = FILES_ROOT / u / name
    if p.exists() and p.is_file():
        p.unlink()
    
    github_sync.backup_to_github_async()
    return redirect(url_for('user_dashboard'))

@app.route('/file/view/<name>')
def file_view(name):
    u = session.get('username')
    if not u:
        return redirect(url_for('login'))
    
    name = secure_filename(name)
    return send_from_directory(FILES_ROOT / u, name, as_attachment=False)

# ============ SERVER CONTROL ============
@app.route('/server/start', methods=['POST'])
def server_start():
    u = session.get('username')
    if not u:
        return jsonify({"ok": False, "msg": "Not logged in"})
    
    fname = secure_filename(request.form.get('file', ''))
    if not fname:
        return jsonify({"ok": False, "msg": "No file specified"})
    
    # Create app ID from filename
    app_id = f"file_{fname.replace('.', '_')}"
    
    # Move file to apps directory
    src = FILES_ROOT / u / fname
    if not src.exists():
        return jsonify({"ok": False, "msg": "File not found"})
    
    app_dir = APPS_ROOT / u / app_id
    app_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy file to apps directory
    shutil.copy2(src, app_dir / fname)
    
    # Detect type from extension
    ext = Path(fname).suffix.lower()
    if ext in ['.py']:
        app_type = 'python'
    elif ext in ['.js', '.mjs']:
        app_type = 'node'
    else:
        return jsonify({"ok": False, "msg": f"Unsupported file type: {ext}"})
    
    # Start process
    ok, msg = process_manager.start_process(u, app_id, app_type)
    if ok:
        return jsonify({"ok": True, "msg": msg})
    else:
        return jsonify({"ok": False, "msg": msg})

@app.route('/server/stop', methods=['POST'])
def server_stop():
    u = session.get('username')
    if not u:
        return jsonify({"ok": False, "msg": "Not logged in"})
    
    # Find and stop all processes for this user
    stopped = 0
    for key in list(process_manager.processes.keys()):
        if key.startswith(f"{u}_"):
            process_manager.stop_process(u, key.replace(f"{u}_", ""))
            stopped += 1
    
    return jsonify({"ok": True, "msg": f"Stopped {stopped} processes"})

@app.route('/server/restart', methods=['POST'])
def server_restart():
    u = session.get('username')
    if not u:
        return jsonify({"ok": False, "msg": "Not logged in"})
    
    # Restart first process
    for key in list(process_manager.processes.keys()):
        if key.startswith(f"{u}_"):
            app_id = key.replace(f"{u}_", "")
            ok, msg = process_manager.restart_process(u, app_id)
            return jsonify({"ok": ok, "msg": msg})
    
    return jsonify({"ok": False, "msg": "No process running"})

@app.route('/server/delete', methods=['POST'])
def server_delete():
    u = session.get('username')
    if not u:
        return jsonify({"ok": False, "msg": "Not logged in"})
    
    # Delete all processes for this user
    deleted = 0
    for key in list(process_manager.processes.keys()):
        if key.startswith(f"{u}_"):
            app_id = key.replace(f"{u}_", "")
            process_manager.stop_process(u, app_id)
            shutil.rmtree(APPS_ROOT / u / app_id, ignore_errors=True)
            deleted += 1
    
    return jsonify({"ok": True, "msg": f"Deleted {deleted} processes"})

@app.route('/logs')
def logs_api():
    u = session.get('username')
    if not u:
        return jsonify({"logs": [], "install": []})
    
    # Get process logs
    all_logs = []
    for key, logs in PROCESS_LOGS.items():
        if key.startswith(f"{u}_"):
            all_logs.extend(logs)
    
    return jsonify({
        "logs": all_logs[-500:],
        "install": []
    })

@app.route('/install', methods=['POST'])
def install():
    u = session.get('username')
    if not u:
        return jsonify({"ok": False, "msg": "Not logged in"})
    
    cmd = request.form.get('command', '').strip()
    if not cmd:
        return jsonify({"ok": False, "msg": "Empty command"})
    
    parts = cmd.split()
    if len(parts) < 3 or parts[1] != 'install':
        return jsonify({"ok": False, "msg": "Format: pip install <module> OR npm install <module>"})
    
    if parts[0] not in ['pip', 'pip3', 'npm']:
        return jsonify({"ok": False, "msg": "Only pip/pip3/npm allowed"})
    
    # Install in user's apps directory
    install_dir = APPS_ROOT / u
    install_dir.mkdir(exist_ok=True)
    
    def install_task():
        try:
            result = subprocess.run(parts, cwd=str(install_dir), capture_output=True, text=True, timeout=60)
            print(f"Install output: {result.stdout}")
        except Exception as e:
            print(f"Install error: {e}")
    
    threading.Thread(target=install_task, daemon=True).start()
    return jsonify({"ok": True, "msg": "Installing in background..."})

# ============ RUN APP ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)