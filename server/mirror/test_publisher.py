import sys,pathlib,tempfile,time,json,base64,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import publisher as p
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes
key=rsa.generate_private_key(public_exponent=65537,key_size=2048);public=key.public_key().public_numbers()
def b(value):return base64.urlsafe_b64encode(value).decode().rstrip('=')
def number(value):return b(value.to_bytes((value.bit_length()+7)//8,'big'))
p._keys={'fixture':{'n':number(public.n),'e':number(public.e)}};p._keys_time=time.time()
tag='v1.0.12';claims={'iss':'https://token.actions.githubusercontent.com','aud':p.AUD,'repository':p.REPO,'repository_id':p.REPO_ID,'ref':'refs/tags/'+tag,'ref_type':'tag','workflow_ref':p.REPO+'/.github/workflows/release.yml@refs/tags/'+tag,'repository_visibility':'public','event_name':'push','iat':time.time()-1,'exp':time.time()+300,'sha':'a'*40}
def signed(c):
 data=b(json.dumps({'alg':'RS256','kid':'fixture'}).encode())+'.'+b(json.dumps(c).encode())
 return data+'.'+b(key.sign(data.encode(),padding.PKCS1v15(),hashes.SHA256()))
assert p.verify(signed(claims),tag)['sha']==claims['sha'];print('PASS authorized release identity')
for name,value in [('repository_id','999'),('aud','wrong'),('ref','refs/heads/main'),('workflow_ref','foreign/workflow'),('exp',time.time()-60),('repository_visibility','private'),('event_name','workflow_dispatch'),('repository','someone/owlpath')]:
 altered=claims|{name:value}
 try:p.verify(signed(altered),tag)
 except Exception:print('PASS reject '+name)
 else:raise AssertionError(name)
bad=signed(claims).split('.');bad[-1]=b(b'bad signature')
try:p.verify('.'.join(bad),tag)
except Exception:print('PASS reject invalid signature')
else:raise AssertionError('bad signature')
with tempfile.TemporaryDirectory() as tmp:
 p.ROOT=pathlib.Path(tmp)/'public';p.INCOMING=pathlib.Path(tmp)/'incoming';p.ROOT.mkdir();p.INCOMING.mkdir();stage=p.INCOMING/tag;stage.mkdir()
 (p.ROOT/'latest.json').write_text(json.dumps({'version':'1.0.9'}));(p.ROOT/'index.html').write_text('previous')
 data={n:n.encode() for n in p.names(tag)}
 for n,v in data.items():(stage/n).write_bytes(v)
 (stage/'release.json').write_text(json.dumps({'version':tag[1:],'source':claims['sha'],'notes':'test'}));(stage/'SHA256SUMS').write_text(''.join(hashlib.sha256(v).hexdigest()+'  '+n+'\n' for n,v in data.items()))
 target=stage/p.names(tag)[0];target.write_bytes(b'corrupt')
 try:p.publish(tag,claims)
 except ValueError:pass
 else:raise AssertionError('corrupt accepted')
 assert (p.ROOT/'index.html').read_text()=='previous';print('PASS corrupt upload retains previous release')
 target.write_bytes(data[target.name]);rename=p.os.rename
 def checked_rename(source,destination):
  assert pathlib.Path(source).parent==p.ROOT and pathlib.Path(destination).parent==p.ROOT/'releases'
  return rename(source,destination)
 p.os.rename=checked_rename
 try:p.publish(tag,claims)
 finally:p.os.rename=rename
 print('PASS atomic rename stays within the public writable mount')
 manifest=json.loads((p.ROOT/'latest.json').read_text());assert manifest['version']==tag[1:] and len(manifest['assets'])==6
 assert all(a['browser_download_url'].startswith('https://ai.z5a.com/') for a in manifest['assets']);print('PASS complete checksummed release publishes first-party manifest')
 assert 'Owlpath '+tag[1:] in (p.ROOT/'index.html').read_text() or tag[1:] in (p.ROOT/'index.html').read_text();print('PASS download page lists the published version')
print('14 publisher checks passed')
