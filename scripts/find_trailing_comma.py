import re
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'templates'/'chats'/'inbox.html'
s=p.read_text(encoding='utf-8')
for i,line in enumerate(s.splitlines(),1):
    if re.search(r',\s*\)',line):
        print('trailing_comma_call at',i,':',line.strip())
print('done')
