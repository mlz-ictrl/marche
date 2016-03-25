Getting started
---------------

After installation all configuration is placed under **/etc/marche**, which
contains the general configuration (:file:`general.conf`) and example files for
many types of services.  See :doc:`config` for detailed information about the
config files and the general config values.

A SYSV init script for the marche server is installed as
:file:`/etc/init.d/marched`.  If you installed the Debian package, it was
automatically added to the boot procedure.

To start the daemon manually, run::

   marched [-c configdir] [-d] [-v]

The config directory is usually ``/etc/marche`` but can be changed by ``-c``.
The ``-d`` switch will daemonize the process, and the ``-v`` switch activates
verbose logging.

The Marche daemon writes logfiles; with the default configuration they go to
``/var/log/marche``, but this can be configured differently.

Additionally, marche's bundled :doc:`graphical user interface <gui>` is
installed as **marche-gui**.

|

You should start now by checking (and possibly changing) the general
configuration (**general.conf**) and configuring your services (see
:doc:`config` and :doc:`jobs`).

Marche's concept of services is that you configure one or more **jobs**, which
can each provide one or more (usually similar) **services**.  For example, the
simple "init-script" job only provides one service, i.e., the service controlled
by the init script it is configured to use.  Other, more high-level, jobs, can
use knowledge of details to scan the system and provide multiple services that
belong together.

To test your configuration, you can start **marche-gui** which will find your
server automatically (if you activated the :ref:`UDP interface <udp-iface>` and
it's within your own network).  If you didn't activate the UDP interface, see
:doc:`gui` for instructions how to add a specific host.
