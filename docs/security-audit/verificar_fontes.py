"""Inventário e busca local de indícios de segredos; não executa o projeto.

Esta busca heurística apoia a revisão humana e não certifica ausência de segredos.
Não imprime valores de credenciais. Requer somente Python e Git locais.
"""
from __future__ import annotations
import ast
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SKIP = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', '.test-tmp', 'backups', 'logs', 'security-audit'}
TEXT = {'.py', '.js', '.mjs', '.cjs', '.html', '.css', '.yaml', '.yml', '.toml', '.json', '.jsonl', '.ndjson', '.md', '.txt', '.env', '.sh', '.ps1', '.tf', '.ini', '.cfg', '.xml', '.key', '.pem'}
PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----'),
    'provider_token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk_(?:live|test)_[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{30,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{20,}|sk-proj-[A-Za-z0-9_-]{30,})\b'),
    'telegram_token': re.compile(r'\b\d{7,12}:[A-Za-z0-9_-]{30,}\b'),
    'jwt': re.compile(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b'),
    'credential_url': re.compile(r'\b[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@', re.I),
    'secret_literal': re.compile(r'''(?i)["']?\b(?:api[_-]?key|brapi_token|telegram_bot_token|access[_-]?token|refresh[_-]?token|client[_-]?secret|jwt[_-]?secret|webhook[_-]?secret|password|passwd|senha|secret[_-]?key)\b["']?\s*[:=]\s*["']([^"'\r\n]+)["']'''),
    'shell_default': re.compile(r'\$\{[A-Za-z_]*(?:TOKEN|KEY|SECRET|PASSWORD|PASSWD)[A-Za-z_]*:-[^}]+\}', re.I),
}

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def scan_text(text, path, object_id=None):
    rows=[]
    for number, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                safe = 'potential'
                if name == 'secret_literal':
                    value=match.group(1)
                    if '${' in value or value in {'token-de-teste', 'test', 'dummy', 'example', 'changeme'}:
                        safe='reference_or_fixture'
                rows.append({'path':path, 'line':number, 'pattern':name, 'classification':safe,
                             'value':'[REDACTED]', **({'blob':object_id} if object_id else {})})
    return rows

def main():
    tracked={p.decode('utf-8') for p in git('ls-files','-z').split(b'\0') if p}
    inventory=[]; current_hits=[]; imports=set(); defs=[]; sink_rows=[]
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if not p.is_file() or set(rel.parts)&SKIP: continue
        if p.suffix.lower() not in TEXT and p.name not in {'.gitignore','.gitattributes','Dockerfile','Makefile'}: continue
        raw=p.read_bytes()
        if b'\0' in raw: continue
        text=raw.decode('utf-8',errors='replace'); name=rel.as_posix()
        inventory.append({'path':name,'lines':len(text.splitlines()),'bytes':len(raw),'tracked':name in tracked,'sha256':hashlib.sha256(raw).hexdigest()})
        current_hits.extend(scan_text(text,name))
        if p.suffix=='.py':
            tree=ast.parse(text,filename=name)
            for n in ast.walk(tree):
                if isinstance(n,ast.Import): imports.update(x.name for x in n.names)
                elif isinstance(n,ast.ImportFrom): imports.add(n.module or '')
                elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    defs.append({'path':name,'line':n.lineno,'name':n.name,'decorators':[ast.unparse(x) for x in n.decorator_list]})
        if p.suffix in {'.html','.js','.mjs','.cjs'}:
            for number,line in enumerate(text.splitlines(),1):
                if re.search(r'innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new\s+Function\b',line):
                    sink_rows.append({'path':name,'line':number,'patterns':sorted(set(re.findall(r'innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval|new\s+Function',line)))})
    objects={}
    for row in git('rev-list','--objects','--all').decode('utf-8',errors='replace').splitlines():
        oid,sep,path=row.partition(' ')
        if sep: objects[oid]=path
    proc=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    history_hits=[]; blob_count=0; history_bytes=0; binary_count=0; text_count=0
    for oid,path in objects.items():
        proc.stdin.write((oid+'\n').encode());proc.stdin.flush()
        head=proc.stdout.readline().decode().split()
        size=int(head[2]);raw=proc.stdout.read(size);proc.stdout.read(1)
        if head[1]!='blob': continue
        blob_count+=1;history_bytes+=size
        if b'\0' in raw[:8192] or Path(path).suffix.lower() in {'.parquet','.xlsx','.png','.jpg','.jpeg','.pdf','.pptx','.zip'}:
            binary_count+=1;continue
        text_count+=1
        history_hits.extend(scan_text(raw.decode('utf-8',errors='replace'),path,oid))
    proc.stdin.close();proc.wait()
    result={'revision':git('rev-parse','HEAD').decode().strip(),
            'commits':int(git('rev-list','--all','--count')),
            'shallow':git('rev-parse','--is-shallow-repository').decode().strip()=='true',
            'refs':git('for-each-ref','--format=%(refname)').decode().splitlines(),
            'tracked_files':len(tracked),'current_text_files_scanned':len(inventory),
            'history_blobs':blob_count,'history_text_blobs_scanned':text_count,
            'history_binary_blobs_excluded':binary_count,'history_bytes':history_bytes,
            'history_scope':'All locally reachable refs, including remote-tracking branches and stash; no fetch, reflog-only or unreachable objects.',
            'current_hits':current_hits,'history_hits':history_hits,
            'imports':sorted(imports),'python_functions':defs,'frontend_sinks':sink_rows,'inventory':inventory,
            'limitations':['Heuristic pattern search, with human triage; no proof of absence.', 'Binary files not decoded for secret hunting.', 'Ignored local logs, backups, environment and audit outputs excluded.']}
    (OUT/'verificacao-fontes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'inventory','imports','python_functions','frontend_sinks','history_hits'}},ensure_ascii=False,indent=2))
    print('History hits:',len(history_hits),Counter((x['path'],x['pattern'],x['classification']) for x in history_hits))

if __name__=='__main__': main()
