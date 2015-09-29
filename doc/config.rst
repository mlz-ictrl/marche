Configuration
-------------

The configuration is done by a single file for the general configuration and several configuration files four your services/jobs.
All configuration files are in INI format.

General configuration of marched
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The general configuration is usually done by **/etc/marche/general.conf**.

general section
+++++++++++++++

user
####

**Default:** None

The user which will be used to run marched.
If no user is given, the current user will be used.

group
#####

**Default:** None

The group which will be used to run marched.
If no group is given, the current group will be used.


piddir
######

**Default:** /var/run

The directory where the pid file (**marched.pid**) will be stored.

logdir
######

**Default:** /var/log

The directory where all the log files will be stored.


Interface configuration
~~~~~~~~~~~~~~~~~~~~~~~

The interface configuration is usually also done by **general.conf**.


interface.xxx sections
++++++++++++++++++++++

Here are all the interfaces configured that should be provided by marched.
For details about configuring the different interfaces, have all at the particular
interface documentation (see: :doc:`iface`).

