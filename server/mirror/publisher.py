#!/usr/bin/env python3
"""Owlpath mirror receiver: accepts a release only from this repository's tag workflow, verified by GitHub OIDC.
No repository token, SSH key or password is stored on the server."""
import base64,fcntl,hashlib,html,json,os,pathlib,re,time,urllib.request,shutil,tempfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding,rsa
REPO='robintheai/owlpath';REPO_ID='1447241699'
AUD='https://ai.z5a.com/owlpath-release-deploy'
SITE='https://ai.z5a.com/clients/owlpath/'
PORT=17013
ROOT=pathlib.Path(os.environ.get('OWLPATH_MIRROR_ROOT','/opt/sspanel/public/clients/owlpath'))
INCOMING=pathlib.Path(os.environ.get('OWLPATH_MIRROR_INCOMING','/opt/sspanel/storage/owlpath-release-incoming'))
_keys={};_keys_time=0

def decode(value):return base64.urlsafe_b64decode(value+'='*(-len(value)%4))
def verify(token,tag):
 global _keys,_keys_time
 if len(token)>16384:raise ValueError('Invalid token')
 header,payload,signature=token.split('.')
 h=json.loads(decode(header));c=json.loads(decode(payload));now=time.time()
 if h.get('alg')!='RS256':raise ValueError('Invalid algorithm')
 if now-_keys_time>600 or (h.get('kid') not in _keys and now-_keys_time>60):
  with urllib.request.urlopen('https://token.actions.githubusercontent.com/.well-known/jwks',timeout=10) as response:
   _keys={k['kid']:k for k in json.load(response)['keys']}
  _keys_time=now
 k=_keys[h['kid']]
 rsa.RSAPublicNumbers(int.from_bytes(decode(k['e']),'big'),int.from_bytes(decode(k['n']),'big')).public_key().verify(decode(signature),(header+'.'+payload).encode(),padding.PKCS1v15(),hashes.SHA256())
 if c.get('iss')!='https://token.actions.githubusercontent.com' or c.get('aud')!=AUD or c.get('repository')!=REPO or str(c.get('repository_id'))!=REPO_ID:raise ValueError('Invalid issuer or repository')
 if c.get('ref')!='refs/tags/'+tag or c.get('ref_type')!='tag' or c.get('workflow_ref')!=REPO+'/.github/workflows/release.yml@refs/tags/'+tag:raise ValueError('Invalid release workflow')
 if c.get('repository_visibility')!='public' or c.get('event_name')!='push':raise ValueError('Invalid workflow event')
 if not now-30<float(c['exp'])<now+900 or float(c.get('nbf',c['iat']))>now+30 or float(c['iat'])<now-900:raise ValueError('Expired token')
 return c

def names(tag):
 v=tag[1:]
 return [f'Owlpath-{v}-{s}-{a}.{e}' for s,e in [('macos','dmg'),('windows','zip')] for a in ['arm64','x64']]+[f'Owlpath-{v}-source.zip']
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while chunk:=f.read(1024*1024):h.update(chunk)
 return h.hexdigest()
def atomic(path,data):
 temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(data);temp.chmod(0o644);os.replace(temp,path)

def page(version):
 v=html.escape(version);base=f'releases/v{v}/Owlpath-{v}-'
 links=''.join(f'<a class="button" href="{base}{f}">{label}</a>' for f,label in [('macos-arm64.dmg','Mac · Apple Silicon'),('macos-x64.dmg','Mac · Intel'),('windows-x64.zip','Windows · x64'),('windows-arm64.zip','Windows · ARM64')])
 return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Owlpath 下载</title>'
  '<style>body{margin:0;background:#0f1a2b;color:#eef2f8;font:16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:720px;margin:auto;padding:48px 24px}'
  'h1{font-size:40px;margin:0 0 8px}p{color:#b9c4d6;line-height:1.7}.button{display:block;margin:12px 0;padding:14px 16px;border-radius:12px;background:#f4c95d;color:#16202f;text-align:center;font-weight:600;text-decoration:none}'
  'small,footer{color:#8d9ab0;font-size:13px;line-height:1.8}a{color:#f4c95d}</style>'
  f'<main><h1>Owlpath</h1><p>给科研人员的极简代理客户端。当前版本 {v}。</p>{links}'
  f'<small>安装包未经 Apple 公证或商业签名，首次打开可能出现系统安全提示。<br><a href="releases/v{v}/SHA256SUMS">校验值</a> · <a href="releases/v{v}/Owlpath-{v}-source.zip">对应版本源码</a> · <a href="https://github.com/robintheai/owlpath">GitHub</a></small>'
  '<footer><p>基于 v2rayN 开源项目 · GPL-3.0</p></footer></main></html>')

def publish(tag,claims):
 stage=INCOMING/tag;expected=names(tag)
 metadata=json.loads((stage/'release.json').read_text())
 if metadata['source']!=claims['sha'] or metadata['version']!=tag[1:]:raise ValueError('Source mismatch')
 sums=(stage/'SHA256SUMS').read_text();checks={}
 for line in sums.splitlines():
  h,n=line.split(maxsplit=1)
  if re.fullmatch('[0-9a-f]{64}',h):checks[n.lstrip('*')]=h
 if set(checks)!=set(expected):raise ValueError('Incomplete release')
 for n in expected:
  if not (stage/n).is_file() or digest(stage/n)!=checks[n]:raise ValueError('Checksum mismatch')
 current=ROOT/'latest.json'
 if current.exists() and tuple(map(int,json.loads(current.read_text())['version'].split('.')))>tuple(map(int,tag[1:].split('.'))):raise ValueError('Cannot roll back current release')
 destination=ROOT/'releases'/tag;destination.parent.mkdir(parents=True,exist_ok=True)
 for n in expected+['SHA256SUMS','release.json']:(stage/n).chmod(0o644)
 stage.chmod(0o755)
 if destination.exists():
  if any(digest(destination/n)!=checks[n] for n in expected):raise ValueError('Published version differs')
 else:
  # The receiver's two writable directories are separate systemd bind mounts.
  # Copy verified files into a private directory inside ROOT before the atomic
  # rename, avoiding EXDEV without widening the service filesystem permissions.
  temporary=pathlib.Path(tempfile.mkdtemp(prefix='.publish-',dir=ROOT))
  try:
   for n in expected+['SHA256SUMS','release.json']:
    shutil.copyfile(stage/n,temporary/n);(temporary/n).chmod(0o644)
   os.rename(temporary,destination);destination.chmod(0o755)
  finally:
   if temporary.exists():shutil.rmtree(temporary)
 base=SITE+'releases/'+tag+'/'
 manifest={'version':tag[1:],'tag_name':tag,'draft':False,'prerelease':False,'body':metadata.get('notes',''),'html_url':SITE,
  'assets':[{'name':n,'browser_download_url':base+n,'digest':'sha256:'+checks[n]} for n in expected]+[{'name':'SHA256SUMS','browser_download_url':base+'SHA256SUMS'}],
  'packages':{n:'/clients/owlpath/releases/'+tag+'/'+n for n in expected},'source':metadata['source']}
 atomic(ROOT/'index.html',page(tag[1:]))
 atomic(current,json.dumps(manifest,ensure_ascii=False,indent=2))
 shutil.rmtree(stage)

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status,data):
  payload=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 def do_POST(self):
  self.connection.settimeout(60)
  match=re.fullmatch(r'/owlpath-release-upload/(v\d+\.\d+\.\d+)/([A-Za-z0-9._-]+)',self.path)
  if not match:return self.reply(404,{'error':'Not found'})
  tag,name=match.groups()
  try:
   auth=self.headers.get('Authorization','')
   if not auth.startswith('Bearer '):raise ValueError('Authentication required')
   claims=verify(auth[7:],tag)
  except Exception as ex:
   reason=str(ex)
   allowed={'Invalid token','Invalid algorithm','Invalid issuer or repository','Invalid release workflow','Invalid workflow event','Expired token'}
   print('Release identity rejected: '+type(ex).__name__+(' '+reason if reason in allowed else ''),flush=True)
   return self.reply(403,{'error':'Release identity rejected'})
  try:
   INCOMING.mkdir(parents=True,exist_ok=True)
   with (INCOMING/'.publish.lock').open('w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    if name=='commit':publish(tag,claims);return self.reply(200,{'version':tag[1:],'published':True})
    if name not in names(tag)+['SHA256SUMS','release.json']:raise ValueError('Unexpected asset')
    length=int(self.headers['Content-Length']);offset=int(self.headers['X-Artifact-Offset']);total=int(self.headers['X-Artifact-Size'])
    limit=65536 if name in ['SHA256SUMS','release.json'] else 1024**3
    if not 0<length<=16*1024*1024 or not 0<total<=limit or not 0<=offset<total or offset+length>total:raise ValueError('Invalid range')
    stage=INCOMING/tag;stage.mkdir(exist_ok=True);target=stage/name
    if offset>(target.stat().st_size if target.exists() else 0):raise ValueError('Missing preceding chunk')
    body=self.rfile.read(length)
    if len(body)!=length:raise ValueError('Incomplete chunk')
    with target.open('r+b' if target.exists() else 'wb') as f:
     f.seek(offset);f.write(body)
     if offset+length==total:f.truncate(total)
    self.reply(200,{'received':offset+length})
  except Exception as ex:
   print('Release write rejected: '+type(ex).__name__+(' errno='+str(ex.errno) if isinstance(ex,OSError) else ''),flush=True)
   self.reply(409,{'error':'Release chunk or commit rejected'})

if __name__=='__main__':
 ROOT.mkdir(parents=True,exist_ok=True);INCOMING.mkdir(parents=True,exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler);server.daemon_threads=True;server.serve_forever()
