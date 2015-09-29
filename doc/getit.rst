Get it
------

Debian package
~~~~~~~~~~~~~~

The marche debian package can be achived from the MLZ debian repository.

To get access, just add the following line to your */etc/apt/sources.list*::

   deb [trusted=yes] https://forge.frm2.tum.de/repos/apt/debian wheezy main extra

**update your package list** and install it via::

   apt-get install marche

Source
~~~~~~

The source can be achived as a read only version via::

   git clone git://forge.frm2.tum.de/home/repos/git/frm2/general/marche.git

and an editable version (if you got the necessary rights) via::

   git clone ssh://forge.frm2.tum.de:29418/frm2/general/marche.git
