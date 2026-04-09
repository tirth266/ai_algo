import glob
for f in glob.glob('backend/api/*.py') + glob.glob('backend/engine/*.py') + glob.glob('backend/routes/*.py') + glob.glob('backend/backtest/*.py'):
    with open(f, 'r', encoding='utf-8') as file:
        c = file.read()
    c = c.replace("{str(e}", "{str(e)}")
    with open(f, 'w', encoding='utf-8') as file:
        file.write(c)
