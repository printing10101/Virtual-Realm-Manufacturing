import os, secrets, sys
from pathlib import Path
# 安全修复：使用随机密钥替代硬编码密钥
os.environ.setdefault('LNN_JWT_SECRET', secrets.token_urlsafe(48))
os.environ.setdefault('LNN_BANNED_TOKENS_FILE', '.lnn_banned_tokens.json')
os.environ.setdefault('APP_ENV', 'development')
REPO = Path('c:/Users/Lenovo/Desktop/灵境制造（上线版）').resolve()
sys.path.insert(0, str(REPO / 'python'))
sys.path.insert(0, str(REPO))
from app.main import app
print('===== Related routes =====', flush=True)
for r in app.routes:
    p = getattr(r, 'path', None)
    if p and ('status' in p or 'dxf' in p.lower() or 'knowledge' in p.lower()):
        methods = getattr(r, 'methods', '?')
        print(f'  {methods} {p}', flush=True)
