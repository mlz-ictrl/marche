Available jobs
--------------

Each section ``[job.xxx]`` in the configuration should configure a single job
from the types below.  (The type is selected by the ``type`` value inside the
section.)

.. _standard-params:

There are two standard parameters supported by all jobs:

.. describe:: permissions

   This selects the permissions for users who want to query or control the job.

   There are three permission levels with increasing capabilities.  Each client
   is assigned one of the levels when it authenticates against the daemon.

   * DISPLAY: to see the job's services, and to query its status, output and log
     files.

   * CONTROL: to be able to start, stop and restart the job.

   * ADMIN: to be able to administrate the job (currently, requesting and
     transferring back config files).

   If not configured differently for a job, these descriptions apply (a client
   that wants to start a job has to have CONTROL level).  However, using the
   ``permissions`` parameter on a job, the required levels can be reassigned.
   The syntax is a comma-separated list of ``actionlevel=userlevel``.

   For example, ``display=control`` means that to do DISPLAY actions (i.e. see
   the job and read its status), the user has to have CONTROL level or higher.
   On the other hand, ``admin=control, control=display`` means that a user who
   has only CONTROL level can configure the service, and a user who has only
   DISPLAY level can start/stop it.

.. describe:: pollinterval

   The interval, in seconds, for Marche to poll the status of all the job's
   services and send it back to clients, if the status changes.

   The default is 3 seconds.  A value of 0 disables polling (not recommended).


The supported job types are:

.. toctree::

   jobs/init
   jobs/process
   jobs/systemd

   jobs/entangle
   jobs/nicos
   jobs/taco
   jobs/tangosrv
