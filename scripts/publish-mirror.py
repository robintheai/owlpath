#!/usr/bin/env python3
"""Upload a verified release to the website mirror with a short-lived GitHub Actions OIDC token."""
import json,os,pathlib,time,urllib.request,urllib.parse,urllib.error
root=pathlib.Path(__file__).resolve().parents[1];tag=os.environ['GITHUB_REF_NAME'];version=tag[1:]
dist=root/'dist'
(dist/'release.json').write_text(json.dumps({'version':version,'source':os.environ['GITHUB_SHA'],'notes':(root/'RELEASE-NOTES.md').read_text()},ensure_ascii=False))
aud='https://ai.z5a.com/owlpath-release-deploy';token=None;issued=0

def identity():
 global token,issued
 if token is None or time.time()-issued>180:
  req=urllib.request.Request(os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']+'&audience='+urllib.parse.quote(aud,safe=''),headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
  with urllib.request.urlopen(req,timeout=30) as response:token=json.load(response)['value']
  issued=time.time()
 return token

def post(name,data,offset=None,total=None):
 for attempt in range(5):
  try:
   headers={'Authorization':'Bearer '+identity(),'Content-Type':'application/octet-stream','User-Agent':'Owlpath-Release/1.0'}
   if offset is not None:headers.update({'X-Artifact-Offset':str(offset),'X-Artifact-Size':str(total)})
   req=urllib.request.Request('https://ai.z5a.com/owlpath-release-upload/'+tag+'/'+name,data=data,headers=headers,method='POST')
   with urllib.request.urlopen(req,timeout=120) as response:return json.load(response)
  except Exception as ex:
   if attempt==4:raise RuntimeError('Mirror publication failed: '+name+' ('+type(ex).__name__+(' '+str(ex.code) if isinstance(ex,urllib.error.HTTPError) else '')+')') from None
   time.sleep(2**attempt)
for path in sorted(dist.iterdir()):
 if not path.is_file() or not (path.suffix in ('.dmg','.zip') or path.name in ('SHA256SUMS','release.json')):continue
 size=path.stat().st_size;offset=0
 with path.open('rb') as f:
  while chunk:=f.read(8*1024*1024):post(path.name,chunk,offset,size);offset+=len(chunk)
 print('Uploaded '+path.name,flush=True)
print(post('commit',b''),flush=True)
