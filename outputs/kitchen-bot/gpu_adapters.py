"""Match DirectML device IDs to real DXGI hardware, preferring discrete GPUs."""
import ctypes as C
import os


class GUID(C.Structure):
    _fields_=[('a',C.c_uint32),('b',C.c_uint16),('c',C.c_uint16),('d',C.c_ubyte*8)]


class Description(C.Structure):
    _fields_=[('name',C.c_wchar*128),('vendor',C.c_uint32),('device',C.c_uint32),
              ('subsystem',C.c_uint32),('revision',C.c_uint32),('dedicated_video',C.c_size_t),
              ('dedicated_system',C.c_size_t),('shared_system',C.c_size_t),
              ('luid_low',C.c_uint32),('luid_high',C.c_int32),('flags',C.c_uint32)]


def _method(pointer,index,result,*arguments):
    table=C.cast(pointer,C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(result,C.c_void_p,*arguments)(table[index])


def enumerate_adapters():
    if os.name!='nt':return []
    dxgi=C.WinDLL('dxgi.dll');d3d=C.WinDLL('d3d12.dll')
    guid=GUID(0x770aae78,0xf26f,0x4dba,(C.c_ubyte*8)(0xa8,0x29,0x25,0x3c,0x83,0xd1,0xb3,0x87))
    device_iid=GUID(0x189819f1,0x1db6,0x4b57,(C.c_ubyte*8)(0xbe,0x54,0x18,0x21,0x33,0x9b,0x85,0xf7))
    dxgi.CreateDXGIFactory1.argtypes=[C.POINTER(GUID),C.POINTER(C.c_void_p)]
    dxgi.CreateDXGIFactory1.restype=C.c_int32
    d3d.D3D12CreateDevice.argtypes=[C.c_void_p,C.c_uint32,C.POINTER(GUID),C.c_void_p]
    d3d.D3D12CreateDevice.restype=C.c_int32
    factory=C.c_void_p()
    if dxgi.CreateDXGIFactory1(C.byref(guid),C.byref(factory))<0:raise RuntimeError('DXGI factory unavailable')
    adapters=[]
    try:
        for index in range(32):
            adapter=C.c_void_p()
            result=_method(factory,12,C.c_int32,C.c_uint32,C.POINTER(C.c_void_p))(factory,index,C.byref(adapter))
            if result<0:break
            try:
                desc=Description()
                if _method(adapter,10,C.c_int32,C.POINTER(Description))(adapter,C.byref(desc))<0:continue
                if desc.flags&2 or d3d.D3D12CreateDevice(adapter,0xb000,C.byref(device_iid),None)<0:continue
                adapters.append({'device':index,'gpu':desc.name,'vendor_id':desc.vendor,
                                 'dedicated_video_bytes':desc.dedicated_video,'api':'DirectX 12'})
            finally:_method(adapter,2,C.c_uint32)(adapter)
    finally:_method(factory,2,C.c_uint32)(factory)
    return adapters


def directml_adapter():
    adapters=enumerate_adapters()
    requested=os.environ.get('COOKING_DML_DEVICE')
    if requested is not None:
        selected=next((a for a in adapters if a['device']==int(requested)),None)
        if selected is None:raise RuntimeError('Requested DirectML GPU unavailable')
        return selected
    if not adapters:raise RuntimeError('No hardware DirectX 12 GPU available')
    return max(adapters,key=lambda a:a['dedicated_video_bytes'])
