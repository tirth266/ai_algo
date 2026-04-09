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

    # Add request: Request to route functions
    content = re.sub(r'(@\w+_router\.(get|post|put|delete)\([^)]+\)\n(?:.*\n)?def )(\w+)\(\):', r'\1\3(request: Request):', content)
    
    # Also fix when it might have other args (though they didn't in flask)
    # This might need some manual adjustments if they had args, but usually in flask it was empty.
    
    # Replace request.args.get -> request.query_params.get
    content = content.replace("request.args.get", "request.query_params.get")
    
    # Replace request.json.get -> (await request.json()).get
    # Since we can't easily await inside sync function, let's just make the function async
    content = re.sub(r'def (\w+)\(request: Request\):', r'async def \1(request: Request):', content)
    content = re.sub(r'request\.json\.get\((.*?)\)', r'(await request.json()).get(\1)', content)
    content = re.sub(r'request\.json', r'(await request.json())', content)
    
    # remove duplicate awaits (if any)
    content = content.replace('await (await request.json())', '(await request.json())')

    # Replace jsonify with returning dict directly
    # Wait, jsonify is already replaced! So no need.
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"Fixed {path}")
