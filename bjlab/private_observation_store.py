"""Private, bounded Windows diagnostic output storage; never an API client.

Only an explicitly selected observation text and its local rejection record are
accepted. Provider envelopes, auth headers, images and credentials are excluded.
There is no plaintext fallback when current-user DPAPI is unavailable.
"""
import base64
import csv
import ctypes
from ctypes import wintypes
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

STORE_VERSION = 'private-r1-output-v1'
DIRECTORY = Path('artifacts/rejected-observation-diagnostics')
RETENTION_SECONDS = 7 * 24 * 60 * 60
MAX_OUTPUT_BYTES = 65_536
MAX_RECORD_BYTES = 262_144
MAX_RECORDS = 32
RECORD_NAME = re.compile(r'[a-f0-9]{32}\.r1diag')
# Model text should never contain credentials. Refuse retention if it does;
# keep its hash only. No environment secrets need to be read to enforce this.
CREDENTIAL_MARKER = re.compile(
    r'sk-[a-zA-Z0-9_-]{12,}|AIza[a-zA-Z0-9_-]{20,}|'
    r'authorization\s*[:=]\s*bearer\s+\S+|x-goog-api-key\s*[:=]\s*\S+', re.I)


class _Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


class WindowsUserProtection:
    """DPAPI current logon identity, UI forbidden, never LOCAL_MACHINE scope."""
    def __init__(self):
        if os.name != 'nt':
            raise PermissionError('Current-user DPAPI is required; no plaintext fallback.')
        self.crypto = ctypes.WinDLL('crypt32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.LocalFree.argtypes = [ctypes.c_void_p]
        self.kernel.LocalFree.restype = ctypes.c_void_p
        common = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p,
                  wintypes.DWORD, ctypes.POINTER(_Blob)]
        self.crypto.CryptProtectData.argtypes = [ctypes.POINTER(_Blob), wintypes.LPCWSTR] + common
        self.crypto.CryptUnprotectData.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p] + common
        self.crypto.CryptProtectData.restype = self.crypto.CryptUnprotectData.restype = wintypes.BOOL

    def _operate(self, data, *, decrypt):
        buffer = ctypes.create_string_buffer(data)
        incoming = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        output = _Blob()
        method = self.crypto.CryptUnprotectData if decrypt else self.crypto.CryptProtectData
        # Same entropy/flags on encryption and decryption; no account/key files.
        if not method(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(output)):
            raise PermissionError('Current-user data protection failed.')
        try:
            return ctypes.string_at(output.data, output.size)
        finally:
            self.kernel.LocalFree(ctypes.cast(output.data, ctypes.c_void_p))

    def protect(self, data):
        return self._operate(data, decrypt=False)

    def unprotect(self, data):
        return self._operate(data, decrypt=True)


def _restrict_directory(directory):
    """Exact DACL: current user and SYSTEM. Changes only this owned directory."""
    if os.name != 'nt':
        raise PermissionError('Protected Windows diagnostic storage is unavailable.')
    whoami = Path(os.environ['SystemRoot'])/'System32/whoami.exe'
    result = subprocess.run([str(whoami), '/user', '/fo', 'csv', '/nh'],
        capture_output=True, text=True, check=True, timeout=5)
    sid = next((field for row in csv.reader(result.stdout.splitlines()) for field in row
                if re.fullmatch(r'S-\d+(?:-\d+)+', field)), None)
    if not sid:
        raise PermissionError('Cannot verify the current Windows identity.')
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                       ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    convert.restype = wintypes.BOOL
    get_dacl = advapi.GetSecurityDescriptorDacl
    get_dacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL),
                        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    get_dacl.restype = wintypes.BOOL
    set_security = advapi.SetNamedSecurityInfoW
    set_security.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    set_security.restype = wintypes.DWORD
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    descriptor, dacl = ctypes.c_void_p(), ctypes.c_void_p()
    present, defaulted = wintypes.BOOL(), wintypes.BOOL()
    sddl = f'D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)'
    if not convert(sddl, 1, ctypes.byref(descriptor), None):
        raise PermissionError('Cannot create the restricted diagnostic DACL.')
    try:
        if not get_dacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)) or not present:
            raise PermissionError('Cannot verify the diagnostic DACL.')
        # SE_FILE_OBJECT, DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION.
        if set_security(str(directory), 1, 0x80000004, None, None, dacl, None):
            raise PermissionError('Cannot restrict diagnostic directory access.')
    finally:
        kernel.LocalFree(descriptor)


def _real_directory(path):
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        raise PermissionError('Diagnostic paths may not be links or junctions.')
    return path


class PrivateObservationStore:
    def __init__(self, workspace_root):
        self.root = Path(workspace_root).resolve(strict=True)
        self.directory = self.root/DIRECTORY
        self.protection = WindowsUserProtection()  # Fail before creating anything.
        ignored = subprocess.run(['git', 'check-ignore', '--quiet', '--no-index', '--', str(self.directory/'probe.r1diag')],
            cwd=self.root, capture_output=True, timeout=5)
        if ignored.returncode:
            raise PermissionError('Diagnostic outputs must be excluded from Git.')
        _real_directory(self.root/'artifacts').mkdir(exist_ok=True)
        _real_directory(self.directory).mkdir(mode=0o700, exist_ok=True)
        self._check_directory()
        _restrict_directory(self.directory)
        self.expiry_cleanup_on_open = self.purge_expired()

    def _check_directory(self):
        _real_directory(self.root/'artifacts'); _real_directory(self.directory)
        if not self.directory.resolve().is_relative_to(self.root):
            raise PermissionError('Diagnostic path escaped the workspace.')

    def _path(self, identifier):
        self._check_directory()
        name = identifier+'.r1diag'
        if not RECORD_NAME.fullmatch(name):
            raise PermissionError('Invalid diagnostic record identifier.')
        path = _real_directory(self.directory/name)
        if path.exists() and path.stat().st_nlink != 1:
            raise PermissionError('Diagnostic records may not be hard links.')
        return path

    def write(self, record):
        self._check_directory()
        # A deliberately narrow record, not an arbitrary provider-response dump.
        if set(record) != {'output_text', 'provenance', 'diagnosis'}:
            raise PermissionError('Only selected observation text and local diagnostics may be retained.')
        text = record['output_text']
        if not isinstance(text, str) or len(text.encode()) > MAX_OUTPUT_BYTES:
            raise ValueError('Observation text exceeds the diagnostic bound.')
        encoded = json.dumps(record, separators=(',', ':'), allow_nan=False).encode()
        if len(encoded) > MAX_RECORD_BYTES or CREDENTIAL_MARKER.search(encoded.decode()):
            raise PermissionError('Unbounded or credential-bearing diagnostic content is not retained.')
        self.purge_expired()
        if len(list(self.directory.glob('*.r1diag'))) >= MAX_RECORDS:
            raise PermissionError('Diagnostic retention capacity reached; explicit expiry purge required.')
        now = int(time.time())
        private = json.dumps({'version': STORE_VERSION, 'created_at': now,
            'expires_at': now+RETENTION_SECONDS, 'record': record}, separators=(',', ':'), allow_nan=False).encode()
        encrypted = self.protection.protect(private)
        identifier = uuid.uuid4().hex
        path = self._path(identifier)
        with path.open('xb') as handle:
            handle.write(encrypted); handle.flush(); os.fsync(handle.fileno())
        return {'retained': True, 'record_id': identifier, 'output_sha256': sha256(text.encode()).hexdigest(),
            'output_bytes': len(text.encode()), 'protection': 'windows-current-user-dpapi',
            'retention_days': 7, 'plaintext_saved': False}

    def _decrypt(self, path):
        if path.stat().st_size > MAX_RECORD_BYTES+4096:
            raise ValueError('Encrypted diagnostic file exceeds the bound.')
        value = json.loads(self.protection.unprotect(path.read_bytes()))
        if (value['version'] != STORE_VERSION or type(value['created_at']) is not int or
                type(value['expires_at']) is not int or
                value['expires_at']-value['created_at'] != RETENTION_SECONDS):
            raise ValueError('Invalid diagnostic retention metadata.')
        return value

    def read(self, identifier):
        value = self._decrypt(self._path(identifier))
        if time.time() >= value['expires_at']:
            raise PermissionError('Diagnostic output expired; explicit purge required.')
        return value['record']

    def purge_expired(self):
        """Explicit, nonrecursive removal of this store's expired encrypted files."""
        self._check_directory(); removed = 0
        for path in self.directory.glob('*.r1diag'):
            if not RECORD_NAME.fullmatch(path.name):
                continue
            checked = self._path(path.stem)
            if time.time() >= self._decrypt(checked)['expires_at']:
                checked.unlink(); removed += 1
        return {'expired_records_removed': removed, 'recursive': False}
