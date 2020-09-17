README for Marche
=================

Intro
-----

Marche is a server control daemon.  You can use it to control services of
different types running on the local host.  There are generic service types like
"an init script" and special types like "an Entangle Tango server".

The Marche daemon allows clients to connect via XMLRPC or other interfaces, to
start/stop/restart services, and to query information about the service like
current status, output or logfiles.  There is also a facility to remotely edit
the configuration file(s) of a service.


Starting
--------

Start the GUI using ``bin/marche-gui``.  It will by default scan the local
network for hosts running a Marche daemon.

You can also give explicit host names to connect to.  The ``-B`` option prevents
the automatic broadcast search for daemons.


The daemon is started with ``bin/marched``, although usually you will want to
start it as a system service with an init script.  Init scripts for Debian and
Red Hat are provided in the ``etc`` directory.


Dependencies
------------

* Python 3.6+
* GUI: PyQt5
* Daemon: PyTango if Tango interface is necessary


Licensing
---------

GUI tool icons by Yusuke Kamiyamane.
Licensed under a Creative Commons Attribution 3.0 License.
See http://p.yusukekamiyamane.com/.

GUI application icon by Claire Jones.
Licensed under a Creative Commons Attribution 3.0 License.
See https://thenounproject.com/hivernoir/.

Uses Material Design CSS, script and icons from Google.
Licensed under the Apache 2.0 License.
See the marche/iface/web/static/LICENSE-APACHE file.
