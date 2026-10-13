"""Keep Selenium's own manager, but never bundle a browser or cached drivers."""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import platform

# Selenium locates its platform manager next to selenium/webdriver/common.
# Collect its packaged data (including manager binaries), never per-user caches.
manager_platform = {'Darwin': 'macos', 'Windows': 'windows',
                    'Linux': 'linux-' + platform.machine().lower()}[platform.system()]
datas, binaries = [], []
for source, destination in collect_data_files('selenium'):
    if source.replace('\\', '/').rsplit('/', 1)[-1] in ('selenium-manager', 'selenium-manager.exe'):
        if destination.replace('\\', '/').endswith('/' + manager_platform):
            binaries.append((source, destination))
    else:
        datas.append((source, destination))
hiddenimports = collect_submodules('selenium')
