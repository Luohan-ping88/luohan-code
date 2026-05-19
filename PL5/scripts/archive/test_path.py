import os

# Simulate the API path calculation
api_file = r"e:\PL5\src\ai\api.py"
project_root = os.path.dirname(os.path.dirname(os.path.dirname(api_file)))
frontend_dir = os.path.join(project_root, "frontend")
login_path = os.path.join(frontend_dir, "login.html")

print("API file:", api_file)
print("Project root:", project_root)
print("Frontend dir:", frontend_dir)
print("Login path:", login_path)
print("Frontend dir exists:", os.path.exists(frontend_dir))
print("Login file exists:", os.path.exists(login_path))
print("Dashboard file exists:", os.path.exists(os.path.join(frontend_dir, "dashboard.html")))
