Graphical user interface
------------------------

Sessions
~~~~~~~~

Sessions can be used to save a list of hosts for later re-use.

Saving
^^^^^^

Create one by either using the menu option `File > Save session as` to save the current session or create it by hand.

Each session is a text file beginning with the line ``Marche session v1``.
Each following line is either a host in the list or a heading entry, which is prefixed with ``Heading:`` and is a non-clickable list entry for grouping.

See the example below:

.. code::

   Marche session v1
   Heading: A heading to group hosts
   host1.example.com
   host2.example.com
   Heading: Another heading
   host3.example.com


Loading
^^^^^^^

Sessions can be loaded with the menu option `File > Load session`.
The option `Default Session` determines which session will be loaded on startup.
You can set it in the `Preferences` window.
