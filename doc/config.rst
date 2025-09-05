Configuration
-------------

For configuration, Marche reads all ``*.conf`` files in its configuration
directory, which is normally ``/etc/marche`` (but can be overridden by invoking
the daemon with the ``-c`` option).  Configuration files are in TOML format, and
all the found files are merged together to form the Marche configuration.

General configuration of marched
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The general configuration is usually placed into a single file named
``/etc/marche/general.conf``.

.. describe:: [general]

   .. _unauth_level:

   .. describe:: unauth_level

      **Default:** ``"display"``

      A permission level (see :ref:`the description of permissions
      <standard-params>`) to assign to users that are not authenticated.

      Can be the special ``"none"`` level to disable everything for these users.


Interface configuration
~~~~~~~~~~~~~~~~~~~~~~~

The interface configuration is usually also done in **general.conf**.

.. describe:: [interface.xxx]

   Each section called ``interface.xxx`` activates and provides configuration
   for an interface with the name ``xxx``.  For details about configuring the
   different interfaces, see :doc:`the interface documentation <iface>`.

   If an interface should just be activated but needs no further configuration,
   just place the section header ``[interface.xxx]``.


Authenticator configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The management of user/password pairs and their respective permission levels is
done by *authenticators*, of which multiple types can be configured in sections.

If no authenticators are configured, the daemon will accept any clients and
assign them the highest permission level.

For details about different authenticators, see :doc:`the authenticator
documentation <auth>`.

.. describe:: [[auth.simple]]

   Each section called ``auth.simple`` configures a simple user/password login.

.. describe:: [auth.pam]

   The ``auth.pam`` section configures authentication against the system.


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


Converting old configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

From Marche version 5, the config file format has changed incompatibly from
INI-style to TOML, and some changes were made to the structure.  This outlines
the changes needed:

* The ``xmlrpc`` interface was renamed to ``rpc``.

* Instead of setting ``interfaces`` in the ``[general]`` section to enable
  interfaces, the presence of an ``[interface.xxx]`` table is enough.
  Conversely, missing such a table disables the interface.

  Therefore, to enable the default set of interfaces (rpc and udp), you need to
  have at least the ``[interface.rpc]`` and ``[interface.udp]`` sections
  present.

* The interface socket bind options ``host`` and ``port`` are now just ``addr``.

* The compatibility behavior to accept ``user`` and ``passwd`` in the
  ``[interface.rpc]`` section has been removed, move those to an
  ``[[auth.simple]]`` table.

* The ``[auth.simple]`` section is now a list of tables (use double brackets:
  ``[[auth.simple]]``).  In this way, multiple username/password pairs are
  possible to configure.

  It is not possible (or required) anymore to use ``[auth.simple#1]``,
  ``[auth.simple#2]`` etc.

* The ``simple`` authenticator now requires passwords to be hashed using bcrypt.

  To hash a password using the Python bcrypt module, use:
  ``bcrypt.hashpw(b"password", bcrypt.gensalt(N))`` where *N* determines how
  many rounds the hash uses; the default is 12, smaller values make the
  authentication faster.

* The ``process``, ``systemd`` and ``init`` jobs don't accept the legacy options
  ``configfile`` and ``logfile``.  You always need to specify files as a list in
  ``configfiles`` and ``logfiles``, respectively.

* The ``binary`` and ``args`` options for the ``process`` job have been combined
  to the ``cmdline`` option.  If you had configured ``binary = a`` and ``args =
  b "c d"``, it now is ``cmdline = ["a", "b", "c d"]``.

* Generally, since TOML is typed, proper types are expected for all non-string
  options.

  - Numeric options like ``pollinterval`` for jobs and ``port`` for various
    interfaces must be float/integer.

  - Boolean options like ``oneshot`` for the ``process`` job must be boolean, not
    strings like "yes" or "no".

  - List of paths like ``logfiles`` and ``configfiles`` must be lists, not
    comma-separated strings.

  - The ``permissions`` option must be a table (dictionary).
