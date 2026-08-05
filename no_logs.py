# no_logs.py - إيقاف جميع الـ logs

import os
import sys
import logging
import warnings

# إيقاف warnings
warnings.filterwarnings("ignore")

# ===== إعادة توجيه stdout/stderr =====
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# ===== تعطيل logging =====
logging.basicConfig(level=logging.CRITICAL)
logging.getLogger().setLevel(logging.CRITICAL)

# تعطيل جميع loggers
for name in logging.root.manager.loggerDict:
    logger = logging.getLogger(name)
    logger.setLevel(logging.CRITICAL)
    logger.disabled = True
    logger.handlers = []

# تعطيل loggers الخاصة بـ uvicorn
logging.getLogger("uvicorn").disabled = True
logging.getLogger("uvicorn.access").disabled = True
logging.getLogger("uvicorn.error").disabled = True

# ===== تعطيل حزم أخرى =====
logging.getLogger("curl_cffi").disabled = True
logging.getLogger("asyncio").disabled = True
