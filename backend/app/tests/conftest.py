import sys
import types

# 为 app/tests 下的用例提供兼容别名：backend.app.* -> app.*
try:
    import app as _app_pkg

    backend_mod = types.ModuleType("backend")
    backend_mod.app = _app_pkg
    sys.modules.setdefault("backend", backend_mod)
    sys.modules.setdefault("backend.app", _app_pkg)

    # 常用子模块按需映射
    import app.services.data_cleanup_service as _svc_cleanup

    sys.modules.setdefault("backend.app.services.data_cleanup_service_v2", _svc_cleanup)
except Exception:
    pass
