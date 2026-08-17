import frida, sys, os, time

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
function hookQueryInterface() {
  waitForModule('nvapi64.dll', function (nv) {
    var qi = nv.getExportByName('nvapi_QueryInterface');
    console.log('HOOK QI at ' + qi);
    Interceptor.attach(qi, {
      onEnter: function (args) { this.id = args[0].toInt32(); },
      onLeave: function (retval) {
        console.log('QI id=' + (this.id>>>0).toString(16) + ' -> ' + retval);
      }
    });
  });
}
function hookLookup() {
  waitForModule('nvapi64_impl.dll', function (m) {
    var lookup = m.base.add(0x102f50);
    console.log('HOOK lookup impl +102f50 at ' + lookup);
    Interceptor.attach(lookup, {
      onEnter: function (args) {
        this.rdx = args[1];
        try { this.id = this.rdx.readU32(); } catch(e) { this.id = -1; }
        console.log('LOOKUP enter id=' + this.id.toString(16));
      },
      onLeave: function (retval) {
        console.log('LOOKUP leave ret=' + retval);
        try { console.log('  -> func_ptr=' + retval.readPointer()); } catch(e) {}
      }
    });
  });
}
hookQueryInterface();
hookLookup();
"""

pid = frida.spawn([target, child])
session = frida.attach(pid)
script = session.create_script(js)
script.on('message', lambda msg, data: print('[frida]', msg))
script.load()
frida.resume(pid)
try:
    os.waitpid(pid, 0)
except Exception:
    time.sleep(3)
session.detach()
