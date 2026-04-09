import glob, re
for f in glob.glob('backend/api/*.py') + glob.glob('backend/engine/*.py') + glob.glob('backend/routes/*.py') + glob.glob('backend/backtest/*.py'):
    with open(f, 'r', encoding='utf-8') as file:
        c = file.read()
    c = re.sub(r'\}\s*\)\s*,\s*\d+', r'}', c)
    c = re.sub(r'\}\s*,\s*\d+\s*\n', r'}\n', c)
    c = re.sub(r'\]\s*,\s*\d+\s*\n', r']\n', c)
    
    # fix the unmatched parenthesis if any exist like "return {"success": {"nested"}), 400"
    c = re.sub(r'\}\s*\)', r'}', c)
    
    with open(f, 'w', encoding='utf-8') as file:
        file.write(c)
