# Monography Code #
---
All the code used in my monography, this repository contains the P4xos version with P4_14
from the USI, the complete repository can be found 
[here](https://github.com/usi-systems/p4xos-public), the code, the dependencies needed are all
in the folder `old-p4xos`.

The version using the P4_16, will be in the folder `new-p4xos`, with all it's dependencies and
code.

The folder `monography` is where all the research reports will remain.

## Running ##
---
All the libs for P4, for some reason I dont know use Python 2.7, so the easiest way to
execute the files without problems, for Linux at least, is to use the python virtualenv.
Fist of all install, install pip2.7, can be installed using the package manager from the
distro, in Arch this will be: 

```bash
$ sudo pacman -S python2-pip
```

With `pip2.7` installed, execute:

```bash
$ pip2.7 install virtualenv --user
$ python2.7 -m virtualenv venv
$ . venv/bin/active
```

This will install virtualenv, create a new environment with name `venv` and start it.
Inside the virtual enviroment, enter the folder you want, old or new, and execute:

```bash
$ make install
```

This will install all dependencies.
