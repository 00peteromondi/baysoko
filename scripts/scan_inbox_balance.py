from pathlib import Path

f=Path(__file__).resolve().parents[1]/'templates'/'chats'/'inbox.html'
print('Scanning',f)
s=f.read_text(encoding='utf-8')
print('backticks:', s.count('`'))
balance=0
for i,ch in enumerate(s):
    if ch=='(':
        balance+=1
    elif ch==')':
        balance-=1
    if balance<0:
        line = s[:i].count('\n')+1
        col = i - s.rfind('\n',0,i)
        print('Negative balance at index',i,'line',line,'col',col)
        break
else:
    print('final balance',balance)
for ln,l in enumerate(s.splitlines(),start=1):
    stripped=l.strip()
    if stripped==')' or stripped==');':
        print('stray closing at line',ln,repr(l))
        break
print('done')
