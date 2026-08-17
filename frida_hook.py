import frida, sys, os, time, subprocess

child = r'C:\Users\SHANA\Downloads\oc_handoff\xbar5090\child_call.py'
target = sys.executable

js = r"""
function waitForModule(name, cb) {
  function check() {
    var m = Process.findModuleByName(name);
    if (m) cb(m); else setTimeout(check, 20);
  }
  check();
}
waitForModule('nvapi64_impl.dll', function (m) {
  var lookup = m.base.add(0x102f50);
  console.log('HOOK lookup at ' + lookup);
  Interceptor.attach(lookup, {
    onEnter: function (args) {
      this.rdx = args[1];
      try {
        this.id = this.rdx.readU32();
      } catch (e) { this.id = -1; }
      console.log('LOOKUP enter id=' + this.id.toString(16));
    },
    onLeave: function (retval) {
      console.log('LOOKUP leave ret=' + retval);
      try {
        var fn = retval.readPointer();
        console.log('  -> func_ptr=' + fn + ' rva=' + fn.sub(m.base));
      } catch (e) {
        console.log('  -> readPointer failed: ' + e);
      }
    }
  });
});
"""

# Spawn child
pid = frida.spawn([target, child])
session = frida.attach(pid)
script = session.create_script(js)
script.on('message', lambda msg, data: print('[frida]', msg))
script.load()
frida.resume(pid)
# wait for child to finish
try:
    os.waitpid(pid, 0)
except Exception as e:
    time.sleep(3)
session.detach()
