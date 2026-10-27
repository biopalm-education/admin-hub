import ast, os
ROOT=os.environ.get('REPO_ROOT','.')
src=open(os.path.join(ROOT,'build_pay.py'),encoding='utf-8').read(); tree=ast.parse(src); keep=[]
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('BTN','LOW','SYS','NOISE','DECLINE','TOLINE','PRICE','BILL') for t in node.targets):
        keep.append(ast.get_source_segment(src,node))
open('rules_pay.py','w',encoding='utf-8').write('import re\n'+'\n'.join(keep)+'\n')
src=open(os.path.join(ROOT,'build_v4.py'),encoding='utf-8').read(); tree=ast.parse(src); keep=[]
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('BTN','GRADE','ASK','SUPPORT','TOPIC') for t in node.targets):
        seg=ast.get_source_segment(src,node)
        keep.append(seg.replace('BTN =','BTN4 =',1) if seg.startswith('BTN') else seg)
open('rules_v4.py','w',encoding='utf-8').write('import re\n'+'\n'.join(keep)+'\n')
import re
w=re.search(r"WEBBOT = re.compile\(r'[^']*'\)", open(os.path.join(ROOT,'fix_roles.py'),encoding='utf-8').read()).group(0)
open('webbot.txt','w',encoding='utf-8').write('import re\n'+w+'\n')
print('rules ok')
