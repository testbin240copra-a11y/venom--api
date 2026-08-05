# no_logs.py

import os
import sys
import logging
import warnings

# ===== إيقاف جميع المخرجات =====
# إعادة توجيه stdout/stderr
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# تعطيل warnings
warnings.filterwarnings("ignore")

# تعطيل logging
logging.basicConfig(level=logging.CRITICAL)
for name in logging.root.manager.loggerDict:
    logger = logging.getLogger(name)
    logger.setLevel(logging.CRITICAL)
    logger.disabled = True
    logger.handlers = []

# تعطيل loggers الخاصة بـ uvicorn
for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "uvicorn.asgi"]:
    logging.getLogger(name).disabled = True

# ===== منع print =====
import builtins
_original_print = builtins.print
def _silent_print(*args, **kwargs):
    pass
builtins.print = _silent_print

# ===== إيقاف sys.excepthook =====
import sys
def _silent_excepthook(exc_type, exc_value, exc_traceback):
    pass
sys.excepthook = _silent_excepthook
