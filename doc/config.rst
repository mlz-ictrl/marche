Configuration
-------------

For configuration, Marche reads all ``*.conf`` files in its configuration
directory, which is normally ``/etc/marche`` (but can be overridden by invoking
the daemon with the ``-c`` option).  Configuration files are in INI format, and
all the found files are merged together to form the Marche configuration.

General configuration of marched
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The general configuration is usually placed into a single file named
``/etc/marche/general.conf``.

.. describe:: [general]

   .. describe:: user

      **Default:** none

      The user as which marched will run.  Normally, this can be kept empty, so
      that the ``root`` user is used, which is necessary for most jobs.  If no
      user is given, the current user on startup will be used.

   .. describe:: group

      **Default:** none

      The group as which marched will run.  If no group is given, the current
      group on startup will be used.

   .. describe:: piddir

      **Default:** ``/var/run``

      The directory where the daemon's pid file (**marched.pid**) will be
      stored.

   .. describe:: logdir

      **Default:** ``/var/log``

      The directory where all the log files will be stored, in a subdirectory
      called ``marche`` and split by day.

   .. describe:: interfaces

      **Default:** ``xmlrpc, udp``

      A comma-separated list of the interfaces that should be started.  A list
      of all available interfaces is given in :doc:`iface`.


Interface configuration
~~~~~~~~~~~~~~~~~~~~~~~

The interface configuration is usually also done in **general.conf**.

.. describe:: [interface.xxx]

   Each section called ``interface.xxx`` provides configuration for an interface
   with the name ``xxx``.  (To be used, interfaces must be enabled in the
   ``interfaces`` value in the ``[general]`` section.)  For details about
   configuring the different interfaces, see :doc:`the interface documentation
   <iface>`.


Authenticator configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The management of user/password pairs and their respective permission levels is
done by *authenticators*, of which multiple types can be configured in sections.

If no authenticators are configured, the daemon will accept any clients and
assign them the highest permission level.

.. describe:: [auth.xxx]

   Each section called ``auth.xxx`` configures an authenticator with the name
   ``xxx``.  For details about different authenticators, see :doc:`the
   authenticator documentation <auth>`.


Job configuration
~~~~~~~~~~~~~~~~~

The configuration for individual jobs is usually placed in separate files.

.. describe:: [job.xxx]

   Each section called ``job.xxx`` configures a job called ``xxx``.

   The job name is arbitrary, but many jobs use it as a default for other
   configuration parameters.  For example, for the ``init`` job, which controls
   services via an init script, the job name is the default value for the name
   of the init script.

   Each job section must have a value named ``type``, which selects the type of
   job to provide.  A list of available job types, and their configuration
   parameters, is given in :doc:`jobs`.
