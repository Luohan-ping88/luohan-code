
import sys
import importlib.util

print('Python:', sys.version)
print('---')

modules = ['requests', 'schedule', 'psutil', 'numpy', 'pandas', 'scipy', 'sklearn']
for m in modules:
    spec = importlib.util.find_spec(m)
    print(f'{m}:', '✓' if spec else '✗')
