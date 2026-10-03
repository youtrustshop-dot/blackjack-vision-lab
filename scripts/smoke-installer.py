"""Install and remove only a fresh, workspace-scoped current-user test app."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import winreg


def exists(key):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key):return True
    except FileNotFoundError:return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    args=parser.parse_args()
    release,work=args.release.resolve(),args.work.resolve()
    registration=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\Blackjack Vision Lab'
    preference=r'Software\bjlab\Blackjack Vision Lab'
    assert not exists(registration) and not exists(preference),'Existing user installation must not be overwritten'
    installer=release/'Blackjack Vision Lab_0.2.0_x64-setup.exe'
    target=(work/('installer-'+uuid.uuid4().hex)).resolve()
    assert target.is_relative_to(work) and not target.exists()
    work.mkdir(parents=True,exist_ok=True)
    install=subprocess.run([str(installer),'/S','/NS','/D='+str(target)],cwd=work,
        timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    assert install.returncode==0
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,registration) as key:
        registered=Path(winreg.QueryValueEx(key,'InstallLocation')[0].strip('"')).resolve()
    assert registered==target
    native=target/'blackjack-vision-lab.exe'
    uninstaller=target/'uninstall.exe'
    assert native.is_file() and uninstaller.is_file()
    assert (target/'licenses/NOTICE.md').is_file()
    original=(release/'Blackjack Vision Lab.exe').read_bytes()
    installed=native.read_bytes()
    marker=b'__TAURI_BUNDLE_TYPE_VAR_'
    assert installed.count(marker+b'NSS')==original.count(marker+b'UNK')==1
    assert installed.replace(marker+b'NSS',marker+b'UNK',1)==original
    hashes={}
    for name in ('bjlab-backend.exe','WebView2Loader.dll'):
        data=(target/name).read_bytes()
        assert data==(release/name).read_bytes()
        hashes[name]=hashlib.sha256(data).hexdigest()
    hashes[native.name]=hashlib.sha256(installed).hexdigest()
    evidence=release/'installer-native-smoke.json'
    try:
        smoke=subprocess.run([sys.executable,str(Path(__file__).with_name('smoke-desktop.py')),
            '--release',str(release),'--work',str(work),'--native','--binary',str(native),
            '--evidence',str(evidence)],cwd=work,timeout=130)
        assert smoke.returncode==0,'Installed executable smoke failed'
    finally:
        # Let the generated uninstaller remove its own declared files. Never
        # recursively delete a computed installation or user AppData directory.
        assert target.is_relative_to(work) and registered==target
        uninstall=subprocess.run([str(uninstaller),'/S'],cwd=work,timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline and (native.exists() or exists(registration)):time.sleep(.1)
        assert uninstall.returncode==0 and not native.exists() and not exists(registration)
        retained=exists(preference)
        if retained:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,preference) as key:
                remembered=Path(winreg.QueryValueEx(key,'')[0].strip('"')).resolve()
                assert remembered==target and winreg.QueryInfoKey(key)[0]==0
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,preference)
        assert not exists(preference) and not target.exists()
    report={'status':'pass','version':'0.2.0','installer':installer.name,
        'installer_sha256':hashlib.sha256(installer.read_bytes()).hexdigest(),
        'installed_file_sha256':hashes,'install_scope':'fresh workspace directory, current user, no shortcuts',
        'existing_user_installation_overwritten':False,'installed_native_proof':evidence.name,
        'native_bundle_marker_change':'Only Tauri UNK -> NSS; all other native bytes identical',
        'install_exit_code':install.returncode,'uninstall_exit_code':uninstall.returncode,
        'owned_installation_and_registry_entries_removed':True,'test_preference_removed':retained}
    (release/'installer-smoke.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
