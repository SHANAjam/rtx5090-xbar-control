import frida, sys, time, subprocess

child_code = r"""
import time
time.sleep(1)
print('slept')
"""
# write child
open(r'C:\Users\SHANA\Downloads\oc_handoff\xbar5090\child_sleep.py','w').write(child_code)
proc = subprocess.Popen([sys.executable, r'C:\Users\SHANA\Downloads\oc_handoff\xbar5090\child_sleep.py'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(0.3)
pid = proc.pid
session = frida.attach(pid)
js = r"""
var k = Process.findModuleByName('kernel32.dll');
var sleep = k.getExportByName('Sleep');
console.log('HOOK Sleep at ' + sleep);
Interceptor.attach(sleep, {
  onEnter: function(args) { console.log('Sleep enter ms=' + args[0]); },
  onLeave: function() { console.log('Sleep leave'); }
});
"""
script = session.create_script(js)
script.on('message', lambda msg, data: print('[frida]', msg))
script.load()
out, err = proc.communicate(timeout=10)
print('out:', out, 'err:', err)
session.detach()
