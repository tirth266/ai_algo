import os
import re

bp_files = [
    'backend/api/broker_routes.py',
    'backend/api/trading_routes.py',
    'backend/backtest/backtest_routes.py',
    'backend/engine/strategy_routes.py',
    'backend/api/journal_routes.py',
    'backend/api/angel_routes.py',
    'backend/routes/reconciliation_routes.py',
    'backend/routes/dashboard_routes.py'
]

for path in bp_files:
    if not os.path.exists(path):
        continue
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix request.query_params.get(..., ..., type=...)
    def type_sub(m):
        key = m.group(1)
        default = m.group(2)
        typ = m.group(3)
        return f'{typ}(request.query_params.get({key}, {default}))'
    
    content = re.sub(r'request\.query_params\.get\(([^,]+),\s*([^,]+),\s*type=([^)]+)\)', type_sub, content)
    
    # Fix return {"success": False, "message": str(e}), 500
    content = re.sub(r'return \{.*?"message": str\(e\}\),\s*500', r'raise HTTPException(status_code=500, detail=str(e))', content)
    content = re.sub(r'return \{.*?"message": f"\{str\(e\)\}"\}\),\s*500', r'raise HTTPException(status_code=500, detail=str(e))', content)
    
    # Any other mismatched dicts: {"success": True, "trades": trades, "count": len(trades})
    content = re.sub(r'len\(([\w_]+)\}\)', r'len(\1)}', content)
    
    # {{ ... }} -> { ... }
    content = re.sub(r'\{\s*\{("success".*?)\}\s*\}', r'{\1}', content)
    content = re.sub(r'return {\n\s*{"success":', r'return {"success":', content)
    content = re.sub(r'\}\n\s*\),\s*200', r'}', content)
    content = re.sub(r'\},\s*200\s*\n', r'}\n', content)
    content = re.sub(r'\}\s*,\s*400', r'', content)
    content = re.sub(r'\(\(await request\.json\(\)\)\(\)\)\.get', r'(await request.json()).get', content)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"Fixed {path}")
