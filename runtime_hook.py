"""
Runtime hook for py2app bundle
"""
print(">> runtime_hook.py executed <<")

import sys
import os
import logging

# Set up logging (only once at the top)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.expanduser("~/agentic_runtime.log"))
    ]
)
logger = logging.getLogger("agentic.runtime")

bundle_lib = os.path.join(os.environ.get('RESOURCEPATH', ''), 'lib', f'python{sys.version_info.major}.{sys.version_info.minor}')
site_pkgs = os.path.join(bundle_lib, 'site-packages')

# Fix if site-packages is mistakenly identified as a zip file
bundle_lib = bundle_lib.replace('.zip', '')
site_pkgs = site_pkgs.replace('.zip', '')

logger.info(f"bundle_lib: {bundle_lib}")
logger.info(f"site_pkgs: {site_pkgs}")

if os.path.exists(site_pkgs):
    sys.path.insert(0, site_pkgs)
    logger.info(f"Inserted site_pkgs into sys.path: {site_pkgs}")
elif os.path.exists(bundle_lib):
    sys.path.insert(0, bundle_lib)
    logger.info(f"Inserted bundle_lib into sys.path: {bundle_lib}")
else:
    logger.error("Neither site-packages nor bundle_lib exists!")

def _get_app_dir():
    if getattr(sys, 'frozen', False) and '.app/Contents/MacOS' in sys.executable:
        return os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
    return os.getcwd()


def force_bundled_libs():
    if getattr(sys, 'frozen', False):
        app_dir = _get_app_dir()
        bundled_lib = os.path.join(app_dir, "Contents", "Resources", "lib", "python3.12")
        if os.path.isdir(bundled_lib):
            sys.path = [p for p in sys.path if "Python.framework" not in p]
            sys.path.insert(0, bundled_lib)
            os.environ["PYTHONHOME"] = bundled_lib
            logger.info("Forced bundled library path: " + bundled_lib)
        else:
            logger.warning("Bundled library directory not found: " + bundled_lib)
    else:
        logger.info("Not running in a frozen environment; no bundled libs to force.")

force_bundled_libs()



def setup_app_environment():
    app_dir = _get_app_dir()
    resources_dir = os.path.join(app_dir, 'Contents', 'Resources') \
        if getattr(sys, 'frozen', False) else os.path.join(app_dir, 'resources')

    logger.info("Application directory: " + app_dir)
    logger.info("Resources directory: " + resources_dir)

    runtime_dir = os.path.join(resources_dir, 'runtime')
    if not os.path.exists(runtime_dir):
        try:
            os.makedirs(runtime_dir, exist_ok=True)
            logger.info("Created runtime directory: " + runtime_dir)
        except Exception as e:
            logger.error("Failed to create runtime directory: " + str(e))
            runtime_dir = os.path.join(os.path.expanduser('~'), '.agentic', 'runtime')
            os.makedirs(runtime_dir, exist_ok=True)
            logger.info("Using fallback runtime directory: " + runtime_dir)

    os.environ['AGENTIC_RUNTIME_DIR'] = runtime_dir
    os.environ['AGENTIC_RESOURCES_DIR'] = resources_dir

    examples_dir = os.path.join(resources_dir, 'resources', 'examples')
    if os.path.isdir(examples_dir):
        os.environ['AGENTIC_EXAMPLES_DIR'] = examples_dir
        logger.info("Found examples directory: " + examples_dir)
    else:
        logger.warning("Examples directory not found at: " + examples_dir)

    dashboard_dir = os.path.join(resources_dir, 'resources', 'dashboard')
    if os.path.isdir(dashboard_dir):
        os.environ['AGENTIC_DASHBOARD_DIR'] = dashboard_dir
        logger.info("Found dashboard directory: " + dashboard_dir)

    return app_dir, resources_dir

app_dir, resources_dir = setup_app_environment()

def adjust_sys_path():
    resources_dir = os.path.join(app_dir, "Contents", "Resources") \
        if getattr(sys, 'frozen', False) else os.path.join(os.getcwd(), "resources")

    bundled_lib = os.path.join(resources_dir, "lib", "python3.12")
    if os.path.isdir(bundled_lib):
        os.environ['PYTHONHOME'] = bundled_lib
        sys.path.insert(0, bundled_lib)
        logger.info("Prepending bundled library path: " + bundled_lib)
    else:
        logger.warning("Bundled library directory not found: " + bundled_lib)

    sys.path = [p for p in sys.path if not (p.startswith("/opt/homebrew") and "Contents/Resources" not in p)]

    logger.info("Adjusted sys.path:")
    for p in sys.path:
        logger.info(p)

adjust_sys_path()
