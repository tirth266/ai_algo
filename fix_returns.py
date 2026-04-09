import glob, re

for f in glob.glob('backend/api/*.py') + glob.glob('backend/engine/*.py') + glob.glob('backend/routes/*.py') + glob.glob('backend/backtest/*.py'):
    with open(f, 'r', encoding='utf-8') as file:
        c = file.read()
    
    # Fix return \n {
    c = re.sub(r'return\s*\n\s*\{', r'return {', c)
    # Fix return \n [
    c = re.sub(r'return\s*\n\s*\[', r'return [', c)
    
    with open(f, 'w', encoding='utf-8') as file:
        file.write(c)
