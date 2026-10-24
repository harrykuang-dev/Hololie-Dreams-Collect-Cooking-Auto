"""Fallback, batching, metadata integrity, and cancellation without a GPU."""
import hashlib
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'outputs/kitchen-bot'))
import inference_backend as backend


class Runtime(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
        self.model=self.directory/'test.onnx';self.model.write_bytes(b'test-model')
        self.metadata={'kind':'classifier','onnx_sha256':hashlib.sha256(b'test-model').hexdigest()}
        self.model.with_suffix('.json').write_text(json.dumps(self.metadata))
        self.environment=patch.dict(os.environ,{'COOKING_STOP_FILE':'','COOKING_TRT_PRECISION':'fp32'})
        self.environment.start()
        self.adapter=patch.object(backend,'directml_adapter',side_effect=RuntimeError('No test GPU'))
        self.adapter.start()

    def tearDown(self):self.adapter.stop();self.environment.stop();self.temp.cleanup()

    def gpu_runtime(self):
        runtime=backend.InferenceRuntime('cpu');runtime.backend='tensorrt'
        runtime.driver=Mock();runtime.trt=Mock()
        return runtime

    def test_cpu_selection_never_probes_or_imports_gpu_libraries(self):
        with patch.object(backend,'_prepare_libraries') as libraries,patch.object(backend,'CudaDriver') as cuda:
            runtime=backend.InferenceRuntime('cpu')
            self.assertEqual(runtime.backend,'cpu');libraries.assert_not_called();cuda.assert_not_called()

    def test_missing_driver_falls_back_to_cpu(self):
        with patch.object(backend,'_prepare_libraries'),patch.object(backend,'CudaDriver',side_effect=OSError('No GPU')):
            runtime=backend.InferenceRuntime('auto')
        self.assertEqual(runtime.backend,'cpu');self.assertIn('No GPU',runtime.reason)

    def test_invalid_backend_is_rejected(self):
        with self.assertRaises(ValueError):backend.InferenceRuntime('unknown')

    def test_metadata_fingerprint_is_checked_before_loading(self):
        self.model.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            backend.ModelSession(self.model,backend.InferenceRuntime('cpu'))

    def test_engine_build_failure_switches_every_model_to_cpu(self):
        runtime=self.gpu_runtime();gpu=Mock()
        with patch.object(backend,'TensorRTSession',side_effect=[gpu,RuntimeError('Unsupported operation')]):
            first=backend.ModelSession(self.model,runtime)
            second=backend.ModelSession(self.model,runtime)
        self.assertEqual(runtime.backend,'cpu');self.assertIsNone(first.gpu);self.assertIsNone(second.gpu)
        gpu.close.assert_called_once()

    def test_runtime_gpu_failure_retries_same_input_on_cpu(self):
        runtime=self.gpu_runtime();gpu=Mock();gpu.infer.side_effect=RuntimeError('GPU unavailable')
        with patch.object(backend,'TensorRTSession',return_value=gpu):session=backend.ModelSession(self.model,runtime)
        pixels=np.ones((3,3,96,96),np.float32)
        with patch.object(session,'_cpu',return_value=np.ones((3,2),np.float32)) as cpu:
            result=session.infer(pixels)
        np.testing.assert_equal(cpu.call_args.args[0],pixels)
        self.assertEqual(result.shape,(3,2));self.assertEqual(runtime.backend,'cpu')
        with patch.object(session,'_cpu',return_value=np.zeros((3,2),np.float32)):
            session.infer(pixels)
        gpu.infer.assert_called_once()

    def test_non_finite_gpu_output_uses_cpu_instead(self):
        runtime=self.gpu_runtime();gpu=Mock();gpu.infer.return_value=np.array([[np.nan]],np.float32)
        with patch.object(backend,'TensorRTSession',return_value=gpu):session=backend.ModelSession(self.model,runtime)
        with patch.object(session,'_cpu',return_value=np.ones((1,2),np.float32)):
            output=session.infer(np.zeros((1,3,96,96)))
        self.assertTrue(np.isfinite(output).all());self.assertEqual(runtime.backend,'cpu')

    def test_incompatible_cached_engine_is_rebuilt_once(self):
        driver=Mock();driver.current.side_effect=lambda:contextlib.nullcontext()
        trt=Mock();engine=Mock();trt.Runtime.return_value.deserialize_cuda_engine.side_effect=[None,engine]
        with patch.object(backend.TensorRTSession,'_serialized_engine',side_effect=[b'old',b'new']) as serialized:
            session=backend.TensorRTSession(self.model,self.metadata,driver,trt,'fp32')
            self.assertEqual(serialized.call_count,2)
            self.assertEqual(serialized.call_args.kwargs,{'rebuild':True})
            self.assertIs(session.engine,engine)
            session.close()

    def test_large_classifier_batches_preserve_input_order(self):
        session=backend.ModelSession(self.model,backend.InferenceRuntime('cpu'))
        array=np.arange(70,dtype=np.float32).reshape(70,1,1,1)
        with patch.object(session,'_cpu',side_effect=lambda batch:batch[:,0,0,:]) as cpu:
            output=session.infer(array)
        self.assertEqual([len(call.args[0]) for call in cpu.call_args_list],[32,32,6])
        np.testing.assert_array_equal(output[:,0],np.arange(70))

    def test_non_finite_output_is_rejected(self):
        session=backend.ModelSession(self.model,backend.InferenceRuntime('cpu'))
        with patch.object(session,'_cpu',return_value=np.array([[np.nan]],np.float32)):
            with self.assertRaisesRegex(RuntimeError,'Non-finite'):session.infer(np.zeros((1,3,96,96)))

    def test_surface_outputs_keep_label_integers_and_confidence(self):
        session=backend.ModelSession(self.model,backend.InferenceRuntime('cpu'))
        labels=np.ones((1,112,112),np.int64);confidence=np.ones((1,112,112),np.float32)*.9
        with patch.object(session,'_cpu',return_value={'labels':labels,'confidence':confidence}) as cpu:
            result=session.infer(np.zeros((1,3,112,112)),('labels','confidence'))
        self.assertEqual(cpu.call_args.args[1],('labels','confidence'))
        self.assertEqual(result['labels'].dtype,np.int64)
        np.testing.assert_array_equal(result['confidence'],confidence)

    def test_surface_gpu_failure_preserves_requested_cpu_outputs(self):
        runtime=self.gpu_runtime();gpu=Mock();gpu.infer.side_effect=RuntimeError('Device lost')
        with patch.object(backend,'TensorRTSession',return_value=gpu):session=backend.ModelSession(self.model,runtime)
        expected={'labels':np.zeros((1,112,112),np.int64),'confidence':np.ones((1,112,112),np.float32)}
        with patch.object(session,'_cpu',return_value=expected) as cpu:
            result=session.infer(np.zeros((1,3,112,112)),('labels','confidence'))
        self.assertIs(result,expected);self.assertEqual(cpu.call_args.args[1],('labels','confidence'))

    def test_cancellation_does_not_turn_into_cpu_loading(self):
        stop=self.directory/'stop';stop.touch()
        with patch.dict(os.environ,{'COOKING_STOP_FILE':str(stop)}):
            with self.assertRaises(InterruptedError):backend.ModelSession(self.model,self.gpu_runtime())

    def test_cancelled_engine_build_propagates(self):
        runtime=self.gpu_runtime()
        with patch.object(backend,'TensorRTSession',side_effect=InterruptedError('Canceled')):
            with self.assertRaises(InterruptedError):backend.ModelSession(self.model,runtime)
        self.assertEqual(runtime.backend,'tensorrt')

    def test_missing_cuda_uses_directml_when_a_real_adapter_exists(self):
        with patch.object(backend,'CudaDriver',side_effect=OSError('No NVIDIA')),\
             patch.object(backend,'directml_adapter',return_value={'device':1,'gpu':'AMD test'}),\
             patch('onnxruntime.get_available_providers',return_value=['DmlExecutionProvider','CPUExecutionProvider']):
            runtime=backend.InferenceRuntime('auto')
        self.assertEqual(runtime.backend,'directml');self.assertEqual(runtime.info['gpu']['device'],1)

    def test_directml_selection_never_probes_cuda(self):
        with patch.object(backend,'CudaDriver') as cuda,\
             patch.object(backend,'directml_adapter',return_value={'device':0,'gpu':'GPU'}),\
             patch('onnxruntime.get_available_providers',return_value=['DmlExecutionProvider']):
            runtime=backend.InferenceRuntime('directml')
        cuda.assert_not_called();self.assertEqual(runtime.backend,'directml')

    def test_directml_failure_retries_cpu_and_does_not_retry_gpu(self):
        runtime=backend.InferenceRuntime('cpu');runtime.requested='directml'
        runtime.backend='directml';runtime.dml_device={'device':1}
        session=backend.ModelSession(self.model,runtime)
        with patch.object(session,'_directml',side_effect=RuntimeError('DML device removed')) as gpu,\
             patch.object(session,'_cpu',return_value=np.ones((1,2),np.float32)) as cpu:
            session.infer(np.zeros((1,3,96,96)));session.infer(np.zeros((1,3,96,96)))
        self.assertEqual(runtime.backend,'cpu');self.assertEqual(gpu.call_count,1);self.assertEqual(cpu.call_count,2)

    def test_tensorrt_failure_retries_directml_with_same_output_names(self):
        runtime=self.gpu_runtime();gpu=Mock();gpu.infer.side_effect=RuntimeError('TRT failed')
        runtime.requested='auto'
        def directml():runtime.backend='directml';runtime.dml_device={'device':1}
        with patch.object(backend,'TensorRTSession',return_value=gpu):session=backend.ModelSession(self.model,runtime)
        expected={'labels':np.zeros((1,112,112),np.int64),'confidence':np.ones((1,112,112),np.float32)}
        with patch.object(runtime,'_enable_directml',side_effect=directml),\
             patch.object(session,'_directml',return_value=expected) as dml:
            result=session.infer(np.zeros((1,3,112,112)),('labels','confidence'))
        self.assertEqual(runtime.backend,'directml');self.assertIs(result,expected)
        self.assertEqual(dml.call_args.args[1],('labels','confidence'))

    def test_directml_nonfinite_output_is_not_returned(self):
        runtime=backend.InferenceRuntime('cpu');runtime.backend='directml';runtime.dml_device={'device':0}
        session=backend.ModelSession(self.model,runtime)
        with patch.object(session,'_directml',return_value=np.array([[np.nan]],np.float32)),\
             patch.object(session,'_cpu',return_value=np.ones((1,2),np.float32)):
            result=session.infer(np.zeros((1,3,96,96)))
        self.assertEqual(runtime.backend,'cpu');self.assertTrue(np.isfinite(result).all())

    def test_directml_fixed_batch_keeps_order_and_reuses_the_session(self):
        runtime=backend.InferenceRuntime('cpu');runtime.backend='directml';runtime.dml_device={'device':1}
        session=backend.ModelSession(self.model,runtime)
        runner=Mock();runner.get_providers.return_value=['DmlExecutionProvider','CPUExecutionProvider']
        runner.run.side_effect=lambda outputs,feeds:[feeds['pixels'][:,0,0,:]]
        with patch('onnxruntime.InferenceSession',return_value=runner) as create:
            for count in (2,7,32):
                pixels=np.arange(count,dtype=np.float32).reshape(count,1,1,1)
                result=session._directml(pixels)
                np.testing.assert_array_equal(result[:,0],np.arange(count))
            create.assert_called_once()
            self.assertTrue(all(len(call.args[1]['pixels'])==32 for call in runner.run.call_args_list))

    def test_directml_silent_cpu_selection_is_rejected(self):
        runtime=backend.InferenceRuntime('cpu');runtime.backend='directml';runtime.dml_device={'device':1}
        session=backend.ModelSession(self.model,runtime)
        runner=Mock();runner.get_providers.return_value=['CPUExecutionProvider']
        with patch('onnxruntime.InferenceSession',return_value=runner):
            with self.assertRaisesRegex(RuntimeError,'silently'):session._directml(np.zeros((1,3,96,96),np.float32))

    def test_precision_cannot_be_downgraded_by_old_environment_setting(self):
        with patch.dict(os.environ,{'COOKING_TRT_PRECISION':'fp16'}):
            session=backend.ModelSession(self.model,backend.InferenceRuntime('cpu'))
        self.assertEqual(session.precision,'fp32')


if __name__=='__main__':unittest.main()
