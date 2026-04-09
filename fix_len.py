import os, glob

for f in glob.glob('backend/api/*.py') + glob.glob('backend/engine/*.py') + glob.glob('backend/routes/*.py'):
    with open(f, 'r') as file:
        c = file.read()
    c = c.replace("len(signals}", "len(signals)}")
    c = c.replace("len(equity_data}", "len(equity_data)}")
    c = c.replace("len(trades}", "len(trades)}")
    
    with open(f, 'w') as file:
        file.write(c)
