import py_compile, glob
files = []
for ext in ['backend/api/*.py', 'backend/engine/*.py', 'backend/routes/*.py', 'backend/backtest/*.py', 'backend/*.py']:
    files.extend(glob.glob(ext))

for f in files:
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        print(f"FAILED: {f}")
        print(e)
print("Finished.")
