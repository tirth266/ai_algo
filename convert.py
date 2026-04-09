import os
import re

def convert_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace Blueprint and Flask stuff with FastAPI defaults
    content = re.sub(r'from flask import Blueprint,\s*jsonify,\s*request.*', 
                     'from fastapi import APIRouter, Request, HTTPException\nfrom pydantic import BaseModel', content)
    content = re.sub(r'from flask_cors.*', '', content)
    
    # Replace Blueprint definition
    content = re.sub(r'(\w+)_bp = Blueprint\([^\,]+,\s*__name__,\s*url_prefix=([^\)]+)\)', 
                     r'\1_router = APIRouter(prefix=\2)', content)
    content = re.sub(r'(\w+)_bp = Blueprint\([^\,]+,\s*__name__\)',
                     r'\1_router = APIRouter()', content)
    
    # Route decorators
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
            method = 'get' # fallback
        return f'@{bp}_router.{method}({path})'
        
    content = re.sub(r'@(\w+)_bp\.route\(([^,]+)(?:,\s*methods=\[([^\]]+)\])?\)', lambda m: route_sub(m) if m.group(3) else f'@{m.group(1)}_router.get({m.group(2)})', content)
    
    # jsonify
    def jsonify_sub(m):
        args = m.group(1)
        if args.startswith('{'):
            return args
        return f'{{{args}}}'
        
    content = re.sub(r'jsonify\((.*?)\)', jsonify_sub, content, flags=re.DOTALL)
    
    content = re.sub(r'return (.*?),\s*200', r'return \1', content)
    
    # Replace parameter request.args.get('limit', 100, type=int)
    # This is manual, FastAPI handles params differently, but we can quickly patch logic 
    # to read from a query parameters explicitly or just let FastAPI parse them from arguments.
    # Actually, the conversion script is too hacky for request.args.get() vs Request.query_params.get().
    # It's better if I just use the convert script to quickly fix it, or we just write a fresh API!
    
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
