Getting started
---------------

After the installation you get all the configuration under **/etc/marche**, which contains the general configuration (**general.conf**)
and example files for types of services. See :doc:`config` for detailed information about the config files and the general config values. 

A init for the marche server is installed as **/etc/init.d/marched**. If you installed the debian package, it was automatically added to
the boot procedure.

Additionally, marche's bundled :doc:`graphical user interface <gui>` is installed as **marche-gui**.

|
|

You should start now by checking (and possibly changing) the general configuration (**general.conf**)
and configuring your services (see :doc:`jobs`).

To test your configuration, you can start **marche-gui** which will find your server automatically (if you activated the
:doc:`udp interface <iface/udp>` and it's within your own network).
If you didn't activate the udp interface, see :doc:`gui` for instructions how to add a specific host.

