import py_compile, glob, json, sys

files = []
for ext in ['backend/api/*.py', 'backend/engine/*.py', 'backend/routes/*.py', 'backend/backtest/*.py', 'backend/*.py']:
    files.extend(glob.glob(ext))

errors = {}
for f in files:
    try:
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        exc = e.exc_value
        errors[f] = {
            'msg': exc.msg,
            'lineno': exc.lineno,
            'text': getattr(exc, 'text', '')
        }
    except Exception as e:
         errors[f] = str(e)

with open('compile_errors.json', 'w') as out:
    json.dump(errors, out, indent=2)
