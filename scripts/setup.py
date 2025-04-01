from setuptools import setup, find_packages
import sys
sys.setrecursionlimit(10000)

# Patch MachO headers to prevent 'header too large' errors
import macholib.MachO
original_sync = macholib.MachO.MachOHeader.synchronize_size

def patched_synchronize_size(self):
    try:
        original_sync(self)
    except ValueError as e:
        print(f"Warning: {e}. Skipping header resize for '{getattr(self, 'filename', 'unknown')}'.")
        pass

macholib.MachO.MachOHeader.synchronize_size = patched_synchronize_size

APP = ['agent_launcher.py']
OPTIONS = {
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleName': 'Agentic',
        'CFBundleDisplayName': 'Agentic',
        'CFBundleIdentifier': 'com.supercog.agentic',
    },
    'argv_emulation': False,
    'packages': find_packages("src"),
    'includes': [
        'agentic',
        'agentic.cli',
        'agentic.runtime',
        'transformers',
        'PyQt5',
        'html',
        'socketserver',
        'typer',
    ],
    'qt_plugins': ['platforms', 'styles'],
    'semi_standalone': True,
    'site_packages': True,
    'excludes': [
        'tkinter', 'matplotlib', 'scipy', 'pytest', 'packaging', 'PyInstaller',
        'typing_extensions', 'backports', 'backports.tarfile',
    ],
    'optimize': 2,
    'strip': False,
}

setup(
    name='Agentic',
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app', 'macholib'],
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=["PyQt5","typer", ],  # Declare PyQt5 explicitly for clarity
)
