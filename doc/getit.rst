Get it
------

Debian package
~~~~~~~~~~~~~~

The Marche debian package can be pulled from the MLZ Debian repository.  To get
access, add the following line to your :file:`/etc/apt/sources.list`::

   deb [trusted=yes] https://forge.frm2.tum.de/repos/apt/debian wheezy main extra

**Update your package list** and install it via ::

   apt-get install marche


Source
~~~~~~

The source can be cloned from the Git repository::

   git clone git://forge.frm2.tum.de/home/repos/git/frm2/general/marche.git

The URI for push access (if you have the necessary rights) is::

   git clone ssh://forge.frm2.tum.de:29418/frm2/general/marche.git
