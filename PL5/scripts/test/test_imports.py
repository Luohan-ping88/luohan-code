import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'import_test.txt')
lines = []
def ti(name):
    try:
        import importlib
        importlib.import_module(name)
        lines.append('PASS ' + name)
    except Exception as e:
        lines.append('FAIL ' + name + ' | ' + str(e)[:150])
        lines.append(traceback.format_exc()[:500])
ti('core.config')
ti('core.data_collector')
ti('core.feature_engineering')
ti('core.models')
ti('core.evaluator')
ti('core.self_learning')
ti('app.auto_scheduler')
ti('monitor.perfect_monitor')
ti('cpp_core')
with open(LOG, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\nDone\n')
