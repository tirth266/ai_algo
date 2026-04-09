import os
import re

def convert_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Flask to FastAPI imports
    content = re.sub(r'from flask import.*', 'from fastapi import APIRouter, Request, HTTPException\nfrom fastapi.responses import JSONResponse', content)
    content = re.sub(r'from flask_cors.*', '', content)
    
    # Blueprint to APIRouter
    content = re.sub(r'(\w+)_bp = Blueprint\([^\,]+,\s*__name__,\s*url_prefix=([^\)]+)\)', 
                     r'\1_router = APIRouter(prefix=\2)', content)
    content = re.sub(r'(\w+)_bp = Blueprint\([^\,]+,\s*__name__\)',
                     r'\1_router = APIRouter()', content)
    
    # Decorators
    def route_sub(m):
        bp, path, methods = m.group(1), m.group(2), m.group(3)
        if 'GET' in methods:
            method = 'get'
        elif 'POST' in methods:
            method = 'post'
        elif 'PUT' in methods:
            method = 'put'
        elif 'DELETE' in methods:
            method = 'delete'
        else:
            method = 'get'
        return f'@{bp}_router.{method}({path})'
        
    content = re.sub(r'@(\w+)_bp\.route\(([^,]+)(?:,\s*methods=\[([^\]]+)\])?\)', lambda m: route_sub(m) if m.group(3) else f'@{m.group(1)}_router.get({m.group(2)})', content)

    # Function defs to async defs with Request param
    content = re.sub(r'\ndef (\w+)\(\):', r'\nasync def \1(request: Request):', content)
    content = re.sub(r'\ndef (\w+)\(([^)]+)\):', r'\nasync def \1(request: Request, \2):', content)
    
    # Fix request.args.get()
    content = content.replace("request.args.get", "request.query_params.get")
    content = re.sub(r'request\.query_params\.get\(([^,]+),\s*([^,)]+),\s*type=\w+\)', r'int(request.query_params.get(\1, \2))', content)

    # Fix request.get_json()
    content = content.replace("request.get_json()", "(await request.json())")
    
    # Fix jsonify()
    def jsonify_sub(m):
        inside = m.group(1)
        if inside.strip() == "":
            return "{}"
        if inside.strip().startswith("{") and inside.strip().endswith("}"):
            return inside
        # if it's kwargs like success=True, foo=bar
        if "=" in inside and "{" not in inside:
            pairs = inside.split(",")
            d = []
            for p in pairs:
                k, v = p.split("=", 1)
                d.append(f'"{k.strip()}": {v.strip()}')
            return "{" + ", ".join(d) + "}"
        return inside
        
    content = re.sub(r'jsonify\((.*?)\)', jsonify_sub, content, flags=re.DOTALL)
    
    # Fix tuple returns: return {...}, 400
    content = re.sub(r'return (\{.*?\})\s*,\s*(\d{3})', lambda m: f'return JSONResponse(status_code={m.group(2)}, content={m.group(1)})', content, flags=re.DOTALL)

    # Additional cleanup for missing request param that might have had other params originally
    content = content.replace("(request: Request, request: Request", "(request: Request")
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

bp_files = [
    'backend/api/broker_routes.py',
    'backend/api/trading_routes.py',
    'backend/backtest/backtest_routes.py',
    'backend/engine/strategy_routes.py',
    'backend/api/journal_routes.py',
    'backend/api/angel_routes.py',
    'backend/routes/reconciliation_routes.py'
]

for f in bp_files:
    if os.path.exists(f):
        convert_file(f)
        print("Converted:", f)
