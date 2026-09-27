import os
with open('app/main.py', 'r') as f:
    code = f.read()

code = code.replace('from fastapi.responses import JSONResponse', 'from fastapi.responses import JSONResponse, HTMLResponse\nimport pathlib')

new_root = '''@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    \"\"\"Serve the interactive dashboard.\"\"\"
    html_path = pathlib.Path(__file__).parent / "dashboard.html"
    return html_path.read_text(encoding="utf-8")

@app.get("/")'''

code = code.replace('@app.get("/")', new_root)

with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(code)

