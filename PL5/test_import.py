import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))
print('Python version:', sys.version)
print('Current directory:', os.getcwd())

try:
    from src.core.config import MODELS_DIR, LOGS_DIR, DATA_DIR
    print('SUCCESS: All imports worked!')
    print('MODELS_DIR:', MODELS_DIR)
    print('LOGS_DIR:', LOGS_DIR)
    print('DATA_DIR:', DATA_DIR)
except Exception as e:
    print('ERROR:', e)
    import traceback
    traceback.print_exc()