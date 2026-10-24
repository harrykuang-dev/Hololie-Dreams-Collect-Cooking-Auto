"""Shared FP32 ONNX models: TensorRT, DirectML, then CPU.

No training framework is imported by this module or either runtime backend.
"""
import contextlib
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import numpy as np
from gpu_adapters import directml_adapter

MODEL_DIRECTORY = Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[2]))/'models/inference'
_DLL_HANDLES = []
_TRT_LOGGER = None


def check_cancelled():
    stop = os.environ.get('COOKING_STOP_FILE')
    if stop and Path(stop).exists():
        raise InterruptedError('Model loading canceled')


def model_path(name):
    name = Path(name)
    if name.is_file() and name.suffix == '.onnx':
        return name.resolve()
    return MODEL_DIRECTORY/(name.stem+'.onnx')


def _prepare_libraries():
    if os.name != 'nt':return
    roots = [Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))]
    roots += [Path(path) for path in sys.path if path]
    for root in roots:
        for suffix in ('', 'tensorrt_libs', 'nvidia/cuda_runtime/bin'):
            directory = root/suffix
            if directory.is_dir():
                _DLL_HANDLES.append(os.add_dll_directory(str(directory)))


class CudaDriver:
    """CUDA Driver API; the NVIDIA driver supplies nvcuda.dll."""
    def __init__(self):
        self.lib = C.WinDLL('nvcuda.dll') if os.name == 'nt' else C.CDLL('libcuda.so.1')
        pointer = C.c_void_p; device_pointer = C.c_uint64
        signatures = {
            'cuInit':[C.c_uint], 'cuDriverGetVersion':[C.POINTER(C.c_int)],
            'cuDeviceGetCount':[C.POINTER(C.c_int)], 'cuDeviceGet':[C.POINTER(C.c_int),C.c_int],
            'cuDeviceGetName':[C.c_char_p,C.c_int,C.c_int],
            'cuDeviceGetAttribute':[C.POINTER(C.c_int),C.c_int,C.c_int],
            'cuDevicePrimaryCtxRetain':[C.POINTER(pointer),C.c_int],
            'cuDevicePrimaryCtxRelease_v2':[C.c_int],
            'cuCtxPushCurrent_v2':[pointer], 'cuCtxPopCurrent_v2':[C.POINTER(pointer)],
            'cuStreamCreate':[C.POINTER(pointer),C.c_uint],
            'cuStreamDestroy_v2':[pointer], 'cuStreamSynchronize':[pointer],
            'cuMemAlloc_v2':[C.POINTER(device_pointer),C.c_size_t],
            'cuMemFree_v2':[device_pointer],
            'cuMemHostAlloc':[C.POINTER(pointer),C.c_size_t,C.c_uint],
            'cuMemFreeHost':[pointer],
            'cuMemcpyHtoDAsync_v2':[device_pointer,pointer,C.c_size_t,pointer],
            'cuMemcpyDtoHAsync_v2':[pointer,device_pointer,C.c_size_t,pointer],
        }
        for name, args in signatures.items():
            function = getattr(self.lib,name); function.argtypes=args;function.restype=C.c_int
        self.call('cuInit',0)
        count=C.c_int();self.call('cuDeviceGetCount',C.byref(count))
        if count.value<1:raise RuntimeError('No NVIDIA CUDA GPU')
        device=C.c_int();self.call('cuDeviceGet',C.byref(device),0);self.device=device.value
        major=C.c_int();minor=C.c_int();version=C.c_int();name=C.create_string_buffer(256)
        self.call('cuDeviceGetAttribute',C.byref(major),75,self.device)
        self.call('cuDeviceGetAttribute',C.byref(minor),76,self.device)
        self.call('cuDriverGetVersion',C.byref(version))
        self.call('cuDeviceGetName',name,256,self.device)
        if (major.value,minor.value)<(7,5):raise RuntimeError('TensorRT requires a Turing or newer GPU')
        self.info={'gpu':name.value.decode(errors='replace'),'compute':f'{major.value}.{minor.value}',
                   'driver_api':version.value,'device':self.device}
        self.context=C.c_void_p();self.call('cuDevicePrimaryCtxRetain',C.byref(self.context),self.device)

    def call(self,name,*arguments):
        result=getattr(self.lib,name)(*arguments)
        if result:raise RuntimeError(f'CUDA {name} failed ({result})')

    @contextlib.contextmanager
    def current(self):
        self.call('cuCtxPushCurrent_v2',self.context)
        try:yield
        finally:
            previous=C.c_void_p();self.call('cuCtxPopCurrent_v2',C.byref(previous))

    def __del__(self):
        if getattr(self,'context',None):
            try:self.call('cuDevicePrimaryCtxRelease_v2',self.device)
            except Exception:pass


class Buffer:
    def __init__(self,driver,size):
        self.driver=driver;self.size=size;self.device=C.c_uint64();self.host=C.c_void_p()
        try:
            driver.call('cuMemAlloc_v2',C.byref(self.device),size)
            driver.call('cuMemHostAlloc',C.byref(self.host),size,0)
            self.array=np.ctypeslib.as_array((C.c_ubyte*size).from_address(self.host.value))
        except BaseException:
            self.close();raise

    def close(self):
        if self.device.value:
            try:self.driver.call('cuMemFree_v2',self.device)
            finally:self.device=C.c_uint64()
        if self.host.value:
            try:self.driver.call('cuMemFreeHost',self.host)
            finally:self.host=C.c_void_p()


class TensorRTSession:
    def __init__(self,path,metadata,driver,trt,precision):
        self.driver=driver;self.trt=trt;self.path=path;self.metadata=metadata
        self.lock=threading.RLock();self.buffers={};self.stream=C.c_void_p()
        global _TRT_LOGGER
        if _TRT_LOGGER is None:_TRT_LOGGER=trt.Logger(trt.Logger.WARNING)
        self.logger=_TRT_LOGGER
        self.runtime=trt.Runtime(self.logger)
        with driver.current():
            serialized=self._serialized_engine(precision)
            self.engine=self.runtime.deserialize_cuda_engine(serialized)
            if self.engine is None:
                serialized=self._serialized_engine(precision,rebuild=True)
                self.engine=self.runtime.deserialize_cuda_engine(serialized)
            if self.engine is None:raise RuntimeError('TensorRT could not deserialize the engine')
            self.context=self.engine.create_execution_context()
            if self.context is None:raise RuntimeError('TensorRT execution context unavailable')
            driver.call('cuStreamCreate',C.byref(self.stream),1)

    def _serialized_engine(self,precision,rebuild=False):
        trt=self.trt
        key={'model':self.metadata['onnx_sha256'],'trt':trt.__version__,
             'precision':precision,'profile':2,'gpu':self.driver.info}
        identifier=hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()
        base=Path(os.environ.get('COOKING_ENGINE_CACHE',str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'CollectCookingAuto/engines')))
        base.mkdir(parents=True,exist_ok=True)
        file=base/(self.path.stem+'-'+identifier[:24]+'.engine');sidecar=file.with_suffix('.json')
        try:
            info=json.loads(sidecar.read_text(encoding='utf-8'));data=file.read_bytes()
            if not rebuild and info['key']==key and hashlib.sha256(data).hexdigest()==info['sha256']:
                return data
        except (OSError,ValueError,KeyError):pass
        check_cancelled()
        print('Building TensorRT engine: '+self.path.stem+' ('+precision+')',flush=True)
        builder=trt.Builder(self.logger)
        network=builder.create_network(1<<int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
        parser=trt.OnnxParser(network,self.logger)
        if not parser.parse_from_file(str(self.path)):
            raise RuntimeError('TensorRT ONNX conversion: '+'; '.join(str(parser.get_error(i)) for i in range(parser.num_errors)))
        config=builder.create_builder_config()
        config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE,512*1024*1024)
        config.builder_optimization_level=2
        if precision!='tf32':config.clear_flag(trt.BuilderFlag.TF32)
        if precision=='fp16':
            if not builder.platform_has_fast_fp16:raise RuntimeError('GPU has no fast FP16 support')
            config.set_flag(trt.BuilderFlag.FP16)
        profile=builder.create_optimization_profile()
        if self.metadata['kind']=='segmenter':
            profile.set_shape('pixels',(1,3,112,112),(1,3,280,448),(1,3,280,448))
        else:profile.set_shape('pixels',(1,3,96,96),(8,3,96,96),(32,3,96,96))
        config.add_optimization_profile(profile)
        class Progress(trt.IProgressMonitor):
            def __init__(self):trt.IProgressMonitor.__init__(self)
            def phase_start(self,name,parent,steps):pass
            def phase_finish(self,name):pass
            def step_complete(self,name,step):
                stop=os.environ.get('COOKING_STOP_FILE')
                return not (stop and Path(stop).exists())
        monitor=Progress();config.progress_monitor=monitor
        serialized=builder.build_serialized_network(network,config)
        check_cancelled()
        if serialized is None:raise RuntimeError('TensorRT engine build failed')
        data=bytes(serialized);info={'key':key,'sha256':hashlib.sha256(data).hexdigest()}
        temporary=file.with_suffix('.pending-'+str(os.getpid()))
        temporary.write_bytes(data);temporary.replace(file)
        temporary=sidecar.with_suffix('.pending-'+str(os.getpid()))
        temporary.write_text(json.dumps(info,indent=2),encoding='utf-8');temporary.replace(sidecar)
        return data

    def _buffer(self,name,shape,dtype):
        size=int(np.prod(shape))*np.dtype(dtype).itemsize
        old=self.buffers.get(name)
        if old is None or old.size<size:
            new=Buffer(self.driver,size)
            if old:old.close()
            self.buffers[name]=new
        buffer=self.buffers[name]
        return buffer,buffer.array[:size].view(dtype).reshape(shape)

    def infer(self,array,outputs=('probabilities',)):
        with self.lock,self.driver.current():
            if not self.context.set_input_shape('pixels',array.shape):raise RuntimeError('Unsupported TensorRT input shape')
            views={}
            for index in range(self.engine.num_io_tensors):
                name=self.engine.get_tensor_name(index)
                shape=array.shape if name=='pixels' else tuple(self.context.get_tensor_shape(name))
                if any(size<=0 for size in shape):raise RuntimeError('Unresolved TensorRT output shape')
                dtype=self.trt.nptype(self.engine.get_tensor_dtype(name))
                buffer,host=self._buffer(name,shape,dtype);views[name]=(buffer,host)
                if not self.context.set_tensor_address(name,buffer.device.value):raise RuntimeError('TensorRT binding failed')
            input_buffer,host_input=views['pixels']
            np.copyto(host_input,array)
            self.driver.call('cuMemcpyHtoDAsync_v2',input_buffer.device,input_buffer.host,host_input.nbytes,self.stream)
            if not self.context.execute_async_v3(stream_handle=self.stream.value):raise RuntimeError('TensorRT execution failed')
            for name in outputs:
                buffer,host=views[name]
                self.driver.call('cuMemcpyDtoHAsync_v2',buffer.host,buffer.device,host.nbytes,self.stream)
            self.driver.call('cuStreamSynchronize',self.stream)
            result={name:views[name][1].copy() for name in outputs}
            return result[outputs[0]] if len(outputs)==1 else result

    def close(self):
        with self.lock,self.driver.current():
            if self.stream.value:self.driver.call('cuStreamSynchronize',self.stream)
            for buffer in self.buffers.values():buffer.close()
            self.buffers.clear()
            if self.stream.value:self.driver.call('cuStreamDestroy_v2',self.stream);self.stream=C.c_void_p()
            self.context=None;self.engine=None;self.runtime=None

    def __del__(self):
        try:self.close()
        except Exception:pass


class InferenceRuntime:
    def __init__(self,backend=None):
        self.sessions=[];self.lock=threading.RLock();self.driver=None;self.trt=None
        self.backend='cpu';self.reason=None;self.dml_device=None;self.failures=[]
        requested=backend or os.environ.get('COOKING_INFERENCE_BACKEND','auto')
        if requested not in ('auto','cpu','tensorrt','directml'):raise ValueError('Invalid inference backend')
        self.requested=requested
        if requested in ('auto','tensorrt'):
            try:
                _prepare_libraries()
                self.driver=CudaDriver()
                import tensorrt as trt
                self.trt=trt;self.backend='tensorrt'
            except Exception as error:self.fallback(error)
        elif requested=='directml':
            self._enable_directml()

    def _enable_directml(self):
        try:
            import onnxruntime as ort
            if 'DmlExecutionProvider' not in ort.get_available_providers():
                raise RuntimeError('DirectML execution provider unavailable')
            self.dml_device=directml_adapter()
            self.backend='directml'
        except Exception as error:
            self.backend='cpu';self.dml_device=None
            self.failures.append(type(error).__name__+': '+str(error))
            self.reason='; '.join(self.failures)

    @property
    def info(self):
        precisions={session.precision for session in self.sessions if session.gpu is not None}
        precision='fp32' if self.backend!='tensorrt' or not precisions else next(iter(precisions)) if len(precisions)==1 else 'mixed'
        return {'backend':self.backend,'requested_backend':self.requested,'precision':precision,
                'gpu':self.driver.info if self.backend=='tensorrt' and self.driver else self.dml_device if self.backend=='directml' else None,
                'tensorrt':self.trt.__version__ if self.trt else None,'fallback_reason':self.reason}

    def fallback(self,error):
        with self.lock:
            failed_backend=self.backend
            self.backend='cpu';self.failures.append(type(error).__name__+': '+str(error))
            self.reason='; '.join(self.failures)
            for session in self.sessions:
                if session.gpu is not None:
                    try:session.gpu.close()
                    except Exception:pass
                    session.gpu=None
                session.dml=None
            if self.requested!='cpu' and failed_backend!='directml':self._enable_directml()
            print('Inference uses '+self.backend+': '+self.reason,flush=True)


class ModelSession:
    def __init__(self,name,runtime=None):
        self.path=model_path(name);self.runtime=runtime or InferenceRuntime()
        self.metadata=json.loads(self.path.with_suffix('.json').read_text(encoding='utf-8'))
        with self.path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=self.metadata['onnx_sha256']:raise ValueError('Model SHA-256 mismatch: '+self.path.name)
        self.gpu=None;self.cpu=None;self.dml=None;self.lock=threading.RLock()
        self.precision='fp32'
        self.runtime.sessions.append(self)
        check_cancelled()
        if self.runtime.backend=='tensorrt':
            try:
                precision=self.precision
                if precision not in ('fp32','fp16','tf32'):raise ValueError('Invalid TensorRT precision')
                self.gpu=TensorRTSession(self.path,self.metadata,self.runtime.driver,self.runtime.trt,precision)
            except InterruptedError:raise
            except Exception as error:self.runtime.fallback(error)

    @property
    def device(self):return self.runtime.backend

    def _cpu(self,array,outputs=('probabilities',)):
        if self.cpu is None:
            import onnxruntime as ort
            options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
            options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.cpu=ort.InferenceSession(str(self.path),sess_options=options,providers=['CPUExecutionProvider'])
        result=self.cpu.run(list(outputs),{'pixels':array})
        return result[0] if len(outputs)==1 else dict(zip(outputs,result))

    def _directml(self,array,outputs=('probabilities',)):
        count=len(array)
        # ResNet eval has no cross-sample operations. A fixed batch avoids
        # compiling a new DirectML graph for each varying candidate count.
        if self.metadata['kind']=='classifier' and count<32:
            array=np.pad(array,((0,32-count),(0,0),(0,0),(0,0)))
        key=tuple(array.shape)
        if self.dml is None:self.dml={}
        if key not in self.dml:
            import onnxruntime as ort
            options=ort.SessionOptions();options.enable_mem_pattern=False
            options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
            options.intra_op_num_threads=2;options.inter_op_num_threads=1
            options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            if self.metadata['kind']=='classifier':options.add_free_dimension_override_by_name('batch',32)
            else:
                options.add_free_dimension_override_by_name('height',array.shape[2])
                options.add_free_dimension_override_by_name('width',array.shape[3])
            providers=[('DmlExecutionProvider',{'device_id':self.runtime.dml_device['device'],
                        'disable_metacommands':'false'}),'CPUExecutionProvider']
            session=ort.InferenceSession(str(self.path),sess_options=options,providers=providers)
            session.disable_fallback()
            if 'DmlExecutionProvider' not in session.get_providers():
                raise RuntimeError('DirectML session silently selected CPU')
            self.dml[key]=session
        result=[value[:count] for value in self.dml[key].run(list(outputs),{'pixels':array})]
        return result[0] if len(outputs)==1 else dict(zip(outputs,result))

    def infer(self,array,outputs=('probabilities',)):
        array=np.ascontiguousarray(array,dtype=np.float32)
        with self.lock:
            pieces=[]
            size=32 if self.metadata['kind']=='classifier' else 1
            for start in range(0,len(array),size):
                batch=array[start:start+size]
                cpu=False
                if self.runtime.backend=='tensorrt' and self.gpu is not None:
                    try:
                        result=self.gpu.infer(batch) if outputs==('probabilities',) else self.gpu.infer(batch,outputs)
                        arrays=result.values() if isinstance(result,dict) else (result,)
                        if not all(np.isfinite(value).all() for value in arrays):raise RuntimeError('Non-finite TensorRT output')
                    except Exception as error:
                        self.runtime.fallback(error);cpu=True
                else:cpu=True
                if cpu and self.runtime.backend=='directml':
                    try:
                        result=self._directml(batch,outputs)
                        arrays=result.values() if isinstance(result,dict) else (result,)
                        if not all(np.isfinite(value).all() for value in arrays):raise RuntimeError('Non-finite DirectML output')
                        cpu=False
                    except Exception as error:self.runtime.fallback(error)
                if cpu:
                    result=self._cpu(batch) if outputs==('probabilities',) else self._cpu(batch,outputs)
                    arrays=result.values() if isinstance(result,dict) else (result,)
                    if not all(np.isfinite(value).all() for value in arrays):raise RuntimeError('Non-finite inference output')
                pieces.append(result)
            if len(pieces)==1:return pieces[0]
            if isinstance(pieces[0],dict):return {name:np.concatenate([piece[name] for piece in pieces],axis=0) for name in outputs}
            return np.concatenate(pieces,axis=0)
