import sys, time, ctypes
time.sleep(2)
sys.path.insert(0, r'C:\Users\SHANA\Downloads\oc_handoff\xbar5090\src')
from xbar5090.nvapi import NvApi, make_buffer, set_u32
api = NvApi()
# GET_INFO
buf = make_buffer(0x20000); set_u32(buf, 0, 0x00015798)
rc = api.call(0xE826E4F0, buf)
print('GET_INFO rc', rc, file=sys.stderr)
# GET_CONTROL
buf2 = make_buffer(0x20000); set_u32(buf2, 0, 0x0001075C)
rc2 = api.call(0xCBFF71D0, buf2)
print('GET_CONTROL rc', rc2, file=sys.stderr)
time.sleep(0.5)
