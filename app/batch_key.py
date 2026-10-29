"""Per-user DPAPI storage; generic batch runners can use RADAR_BATCH_KEY instead."""
import ctypes
import os
from pathlib import Path

KEY_FILE=Path(__file__).resolve().parent.parent/'data'/'batch-key.dpapi'
class Blob(ctypes.Structure):
    _fields_=[('size',ctypes.c_ulong),('data',ctypes.POINTER(ctypes.c_ubyte))]

def crypt(value,protect):
    if os.name!='nt':raise RuntimeError('Use RADAR_BATCH_KEY on non-Windows runners')
    buffer=ctypes.create_string_buffer(value)
    source=Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));result=Blob()
    fn=ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(result)):raise ctypes.WinError()
    try:return ctypes.string_at(result.data,result.size)
    finally:ctypes.windll.kernel32.LocalFree(result.data)

def read_key():
    value=os.environ.get('RADAR_BATCH_KEY')
    if value:return value
    if KEY_FILE.exists():return crypt(KEY_FILE.read_bytes(),False).decode()
    raise RuntimeError('Batch publisher credential is not configured')

if __name__=='__main__':
    import getpass
    value=getpass.getpass('Collector key (hidden): ')
    if len(value)<32:raise ValueError('Invalid collector key')
    KEY_FILE.parent.mkdir(exist_ok=True)
    KEY_FILE.write_bytes(crypt(value.encode(),True))
    print('Collector credential protected for this Windows user.')
