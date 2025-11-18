import sys
sys.path.insert(0, r'D:\PycharmProjects\Tourist03_win')
import importlib
mod = importlib.import_module('app')
app = getattr(mod, 'app')
paths = sorted({getattr(r, 'path', '') for r in app.routes})
for p in paths:
    print(p)
print('--- routes count:', len(paths))
