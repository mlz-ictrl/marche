Introduction
------------

The Marche daemon provides a way to control system services via several remote
interfaces.  It is written in Python and was originally developed to control
system services at the FRM-II_/MLZ_ neutron source.

The main features are:

- Authenticated remote access for starting, stopping and restarting services
- Access via multiple interfaces at the same time
- Transfer of log files of the different services to the clients
- Editing of configuration files on the client side
- Possibility to handle many types of service with customized jobs
- Graphical client usable by non-admins


.. _FRM-II: http://www.frm2.tum.de/
.. _MLZ: http://mlz-garching.de/
