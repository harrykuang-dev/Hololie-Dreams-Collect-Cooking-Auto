"""Explicit model loading must never imply permission to start gameplay."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'outputs/kitchen-bot')]
import gui
from radius_policy import exposed_radius
from collections import Counter


class Listener:
    def __init__(self,*args):self.enabled=False
    def configure(self,**kwargs):self.enabled=kwargs.get('enabled',self.enabled)
    def start(self):pass
    def close(self):pass


class Process:
    def __init__(self,*args,**kwargs):self.command=args[0];self.code=None
    def poll(self):return self.code


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patches=[patch.object(gui,'DATA',Path(self.temp.name)),
                      patch.object(gui,'GlobalHotkey',Listener),
                      patch.object(gui,'window_scale',lambda root:1.0),
                      patch.object(gui,'request_game_foreground'),
                      patch.object(gui.subprocess,'Popen',Process)]
        for item in self.patches:item.start()
        self.root=tk.Tk();self.root.withdraw()
        self.app=gui.CookingApp(self.root);self.root.update_idletasks()

    def tearDown(self):
        if self.app.stream:self.app.stream.close()
        self.app.child=None
        self.app.destroy()
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()

    def ready(self):
        self.app.load_models()
        gui.publish_state(self.app.state_path,'ready')
        self.app.poll()
        self.assertEqual(self.app.run_state,'ready')

    def test_idle_and_loading_hotkeys_cannot_start(self):
        app=self.app
        self.assertTrue(app.start_button.instate(['disabled']))
        self.assertFalse(app.start_listener.enabled)
        app.messages.put(('start',None));app.poll()
        self.assertIsNone(app.child)
        app.load_models()
        self.assertIn('--wait-for-start',app.child.command)
        self.assertNotIn('--autostart',app.child.command)
        app.messages.put(('start',None));app.poll()
        app.start()
        self.assertFalse(app.start_path.exists())
        self.assertEqual(app.run_state,'loading')

    def test_model_ready_is_separate_from_actual_start(self):
        self.ready();app=self.app
        self.assertFalse(app.start_path.exists())
        self.assertTrue(app.start_listener.enabled)
        self.assertTrue(app.load_button.instate(['disabled']))
        app.start()
        self.assertEqual(json.loads(app.start_path.read_text()),{'start':True})
        self.assertEqual(app.run_state,'starting')
        self.assertFalse(app.start_listener.enabled)
        self.assertEqual(app.toggle_path.read_text(),'0')

    def test_explicit_start_requests_focus_before_releasing_worker(self):
        self.ready();app=self.app
        def activate():
            self.assertFalse(app.start_path.exists())
            self.assertEqual(app.run_state,'ready')
            return False  # Windows may deny activation; the worker waits safely.
        with patch.object(gui,'request_game_foreground',side_effect=activate) as focus:
            app.start()
            focus.assert_called_once_with()
        self.assertTrue(app.start_path.exists())
        self.assertEqual(app.run_state,'starting')

    def test_loading_help_and_stopped_states_do_not_request_focus(self):
        app=self.app
        with patch.object(gui,'request_game_foreground') as focus:
            app.start()
            app.load_models();app.start()
            focus.assert_not_called()
        gui.publish_state(app.state_path,'ready');app.poll()
        with patch.object(gui,'request_game_foreground') as focus:
            app.show_model_help();app.start()
            app.close_model_help();app.stop();app.start()
            focus.assert_not_called()

    def test_help_disables_start_and_preserves_loaded_model(self):
        self.ready();app=self.app
        child=app.child
        app.show_model_help();app.start()
        self.assertFalse(app.start_path.exists())
        self.assertFalse(app.start_listener.enabled)
        self.assertTrue(app.start_button.instate(['disabled']))
        app.close_model_help()
        self.assertIs(app.child,child)
        self.assertTrue(app.start_listener.enabled)

    def test_stop_before_start_unloads_without_a_start_request(self):
        self.ready();app=self.app
        app.stop()
        self.assertTrue(app.stop_path.exists())
        self.assertFalse(app.start_path.exists())
        app.child.code=0;app.poll()
        self.assertIsNone(app.child)
        self.assertTrue(app.start_button.instate(['disabled']))
        self.assertTrue(app.load_button.instate(['!disabled']))
        app.model.set('resnet101');app.load_models()
        self.assertIn('resnet101',app.child.command)

    def test_language_change_preserves_progress_and_state(self):
        self.ready();app=self.app
        app.completed=3
        for language in gui.TEXT:
            app.language.set(language);app.translate()
            self.assertEqual(app.run_state,'ready')
            self.assertIn('3 /',app.count.cget('text'))
            self.assertEqual(app.load_button.cget('text'),gui.UI[language]['load'])
            self.assertTrue(app.start_button.instate(['!disabled']))

    def test_capture_prompt_is_display_only_and_cancel_restores_saved_key(self):
        app=self.app
        for language in gui.TEXT:
            app.language.set(language);app.translate()
            for variable,display,entry in zip((app.start_key,app.stop_key),(app.start_display,app.stop_display),app.shortcut_entries):
                previous=variable.get()
                app.begin_capture(SimpleNamespace(widget=entry),variable)
                self.assertEqual(display.get(),app.tr('capture'))
                self.assertEqual(variable.get(),previous)
                app.save_settings()
                settings=json.loads((gui.DATA/'settings.json').read_text(encoding='utf8'))
                self.assertEqual(settings['start_key'],app.start_key.get())
                self.assertEqual(settings['stop_key'],app.stop_key.get())
                app.end_capture(SimpleNamespace(widget=entry))
                self.assertEqual(display.get(),previous)

    def test_old_field_focus_out_cannot_cancel_capture_in_new_field(self):
        app=self.app;first,second=app.shortcut_entries
        app.begin_capture(SimpleNamespace(widget=first),app.start_key)
        app.begin_capture(SimpleNamespace(widget=second),app.stop_key)
        app.end_capture(SimpleNamespace(widget=first))
        self.assertIs(app.capturing,app.stop_key)
        self.assertEqual(app.stop_display.get(),app.tr('capture'))
        app.cancel_capture(SimpleNamespace(widget=app.games_entry))
        self.assertIsNone(app.capturing)
        self.assertEqual(app.stop_display.get(),'Esc')

    def test_num_lock_capture_does_not_add_alt_but_real_alt_is_retained(self):
        app=self.app;entry=app.shortcut_entries[0]
        for state,expected in ((0x8,'F8'),(0xC,'Ctrl+F8'),(0x20008,'Alt+F8'),(0x2000D,'Ctrl+Alt+Shift+F8')):
            app.begin_capture(SimpleNamespace(widget=entry),app.start_key)
            app.capture_key(SimpleNamespace(keysym='F8',state=state,keycode=0x77))
            self.assertEqual(app.start_key.get(),expected)
            self.assertEqual(app.start_display.get(),expected)
            self.assertIsNone(app.capturing)

    def test_modifier_only_keeps_waiting_without_changing_setting(self):
        app=self.app;entry=app.shortcut_entries[0]
        app.begin_capture(SimpleNamespace(widget=entry),app.start_key)
        app.capture_key(SimpleNamespace(keysym='Alt_L',state=0x20008,keycode=0x12))
        self.assertEqual(app.start_key.get(),'F8')
        self.assertEqual(app.start_display.get(),app.tr('capture'))
        self.assertIs(app.capturing,app.start_key)


class WorkerGate(unittest.TestCase):
    def test_stop_wins_over_an_existing_start_request(self):
        with tempfile.TemporaryDirectory() as folder:
            start=Path(folder)/'start.json';stop=Path(folder)/'stop'
            start.write_text('{"start":true}');stop.touch()
            self.assertFalse(gui.wait_for_start(start,stop))

    def test_wait_remains_blocked_until_explicit_start(self):
        with tempfile.TemporaryDirectory() as folder:
            start=Path(folder)/'start.json';stop=Path(folder)/'stop'
            result=[]
            thread=threading.Thread(target=lambda:result.append(gui.wait_for_start(start,stop)))
            thread.start()
            try:
                time.sleep(.08);self.assertTrue(thread.is_alive());self.assertEqual(result,[])
                start.write_text('{"start":true}')
                thread.join(2);self.assertEqual(result,[True])
            finally:
                stop.touch();thread.join(2)

    def test_both_models_use_same_65_percent_policy_with_protections(self):
        for original,expected in [(20,13),(14,10),(12,10),(10,10)]:
            candidate={'label':'ham','radius':expected,'local_classifier':{'label':'ham','score':1.0}}
            result,_=exposed_radius(candidate,original,human=True,active={'ham'},
                                   counters=[3],recipe=['ham'],inventory=Counter())
            self.assertEqual(result,expected)
        for label,score,active in [('moyashi',1.,{'moyashi'}),('ham',.99,{'ham'}),('ham',1.,set())]:
            result,_=exposed_radius({'label':label,'radius':13,'local_classifier':{'label':label,'score':score}},
                                   20,human=True,active=active,counters=[3],recipe=[label],inventory=Counter())
            self.assertEqual(result,20)


class ForegroundGate(unittest.TestCase):
    def test_async_restore_finishes_before_capture_adapter_is_used(self):
        import standalone
        desktop=SimpleNamespace(should_stop=lambda:False,focused=lambda:True,close=lambda:None)
        with tempfile.TemporaryDirectory() as folder:
            args=['standalone.py','--games','1','--wait-for-focus','--output',folder]
            with patch.object(sys,'argv',args),\
                 patch.object(standalone,'Desktop',side_effect=[RuntimeError('Game window minimized: hololive-Dreams'),desktop]) as create,\
                 patch.object(standalone,'advance_to_order',return_value=True) as transition,\
                 patch.object(standalone,'play',return_value={'natural_end':True}),\
                 patch.dict(gui.os.environ,{'COOKING_STOP_FILE':''}):
                standalone.main(model=SimpleNamespace())
                self.assertEqual(create.call_count,2)
                self.assertIs(transition.call_args.args[0],desktop)

    def test_explicit_start_waits_for_game_foreground_and_reuses_models(self):
        import standalone
        states=[];checks=[]
        class Desktop:
            foreground=False
            def __init__(self,title):self.polls=0
            def should_stop(self):return False
            def focused(self):
                self.polls+=1;self.foreground=self.polls>=3
                checks.append(self.foreground);return self.foreground
            def close(self):pass
        def advance(desktop,*args):
            self.assertTrue(desktop.foreground)
            return True
        with tempfile.TemporaryDirectory() as folder:
            args=['standalone.py','--games','1','--wait-for-focus','--output',folder]
            model=type('LoadedModel',(),{})()
            with patch.object(sys,'argv',args),patch.object(standalone,'Desktop',Desktop),\
                 patch.object(standalone,'load_models',side_effect=AssertionError('Models loaded twice')),\
                 patch.object(standalone,'advance_to_order',side_effect=advance) as transition,\
                 patch.object(standalone,'play',return_value={'natural_end':True}) as play,\
                 patch.dict(gui.os.environ,{'COOKING_STOP_FILE':''}):
                standalone.main(model=model,status_callback=states.append)
                transition.assert_called_once();play.assert_called_once()
                self.assertIs(play.call_args.args[1],model)
        self.assertEqual(checks,[False,False,True])
        self.assertEqual(states,['waiting_focus','running'])

    def test_cancel_while_game_window_is_missing_never_advances(self):
        import standalone
        with tempfile.TemporaryDirectory() as folder:
            stop=Path(folder)/'stop'
            def missing(title):
                stop.touch();raise RuntimeError('Game window not found: '+title)
            args=['standalone.py','--games','1','--wait-for-focus','--output',folder]
            with patch.object(sys,'argv',args),patch.object(standalone,'Desktop',side_effect=missing),\
                 patch.object(standalone,'advance_to_order') as transition,patch.object(standalone,'play') as play,\
                 patch.dict(gui.os.environ,{'COOKING_STOP_FILE':str(stop)}):
                standalone.main(model=object())
                transition.assert_not_called();play.assert_not_called()


if __name__=='__main__':unittest.main()
