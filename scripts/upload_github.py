import os
import sys
import base64
import json
import urllib.request
import urllib.error

TOKEN = os.getenv("GH_PAT")
USER = os.getenv("GH_USER")
REPO = "fx-pulse"

if not TOKEN or not USER:
    print("Error: Credenciales no provistas.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "FX-Pulse-Uploader"
}

def make_request(url, data=None, method="GET"):
    req = urllib.request.Request(url, headers=HEADERS, method=method)
    if data:
        req.data = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, json.loads(body) if body else {}
    except Exception as e:
        return 500, {"message": str(e)}

# 1. Crear repo si no existe
print(f"Verificando repositorio {USER}/{REPO}...")
status, resp = make_request(f"https://api.github.com/repos/{USER}/{REPO}")
if status == 404:
    print(f"Creando nuevo repositorio publico '{REPO}'...")
    create_payload = {
        "name": REPO,
        "description": "FX-Pulse: Real-time Quantitative FX Radar, Multi-pair Analytics & Interactive Dashboard",
        "private": False,
        "auto_init": False
    }
    status, resp = make_request("https://api.github.com/user/repos", data=create_payload, method="POST")
    if status in (200, 201):
        print(f"✅ Repositorio creado exitosamente en GitHub.")
    else:
        print(f"❌ Error al crear repositorio: {status} - {resp}")
        sys.exit(1)
elif status == 200:
    print(f"Repositorio {REPO} ya existe en tu cuenta.")
else:
    print(f"Respuesta inesperada al verificar repo: {status} - {resp}")
    sys.exit(1)

# 2. Recorrer archivos locales de fx_pulse y subirlos
base_dir = os.path.abspath("fx_pulse")
files_to_upload = []

for root, dirs, files in os.walk(base_dir):
    # Ignorar carpetas del .gitignore
    if any(ign in root.split(os.sep) for ign in ["cache", "output", "__pycache__", ".venv", ".pytest_cache"]):
        continue
    for file in files:
        if file in [".env", "fx_cache.db"]:
            continue
        full_path = os.path.join(root, file)
        rel_path = os.path.relpath(full_path, base_dir).replace("\\", "/")
        files_to_upload.append((full_path, rel_path))

print(f"Subiendo {len(files_to_upload)} archivos al repositorio...")

for full_path, rel_path in files_to_upload:
    with open(full_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    # Verificar si el archivo ya existe para obtener sha
    get_status, get_resp = make_request(f"https://api.github.com/repos/{USER}/{REPO}/contents/{rel_path}")
    put_payload = {
        "message": f"feat: add {rel_path}",
        "content": content_b64
    }
    if get_status == 200 and "sha" in get_resp:
        put_payload["sha"] = get_resp["sha"]

    put_status, put_resp = make_request(f"https://api.github.com/repos/{USER}/{REPO}/contents/{rel_path}", data=put_payload, method="PUT")
    if put_status in (200, 201):
        print(f"  ✅ Subido: {rel_path}")
    else:
        print(f"  ❌ Error subiendo {rel_path}: {put_status} - {put_resp.get('message')}")

print("\n🎉 Todos los archivos han sido desplegados y sincronizados en GitHub.")
print(f"URL del Repositorio: https://github.com/{USER}/{REPO}")
