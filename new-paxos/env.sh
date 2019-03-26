#!/bin/bash -e

# Print script commands.
set -x
# Exit on errors.
set -e

env_dir=$PWD/../environment

cd $env_dir

if [ 1 -eq 0]; then
  echo "Starting mininet script installation"

  sudo rm -rf mininet
  git clone git://github.com/mininet/mininet mininet
  cd mininet
  git tag
  git checkout -b 2.2.1 2.2.1
  cd ..
  mininet/util/install.sh -a
fi

pip2.7 install git+https://github.com/mininet/mininet.git

cd $env_dir
rm -rf pox
git clone http://github.com/noxrepo/pox pox
cd pox
git checkout -B ad-net f95dd1a81584d716823bbf565fa68254416af603

cd $env_dir
echo "Starting bmv2 script"

sudo rm -rf bmv2 p4c-bmv2 behavioral-model p4c-bm

echo "Cloning repos"
git clone https://github.com/p4lang/behavioral-model.git bmv2
git clone https://github.com/p4lang/p4c-bm.git p4c-bmv2

if [ 1 -eq 0]; then
  # Install thrift
  echo "Starting thrift installation"
  sudo apt-get install -y libboost-dev libboost-test-dev libboost-program-options-dev \
  libboost-filesystem-dev libboost-thread-dev libevent-dev automake libtool \
  flex bison pkg-config g++ libssl-dev
  tmpdir=`mktemp -d -p .`
  cd $tmpdir

  wget https://www.apache.org/dist/thrift/0.9.3/thrift-0.9.3.tar.gz
  tar -xvf thrift-0.9.3.tar.gz
  cd thrift-0.9.3
  ./configure --with-cpp=yes --with-c_glib=no --with-java=no --with-ruby=no \
  --with-erlang=no --with-go=no --with-nodejs=no
  sudo make -j4
  sudo make install
  cd ..

  # install nanomsg
  echo "Installing nanomsg"
  sh ../bmv2/travis/install-nanomsg.sh
  sudo ldconfig


  # install nnpy
  echo "Installing nnpy"
  sh bmv2/travis/install-nnpy.sh

  # clean up
  echo "Cleaning up"
  cd ..
  sudo rm -rf $tmpdir
fi

echo "Installing BMv2"
cd bmv2
./autogen.sh
./configure --enable-debugger
sudo make

echo "Installing P4 BMv2"
cd ../p4c-bmv2
pip2.7 install -r requirements.txt
pip2.7 install -r requirements_v1_1.txt
python2.7 setup.py install

echo "Installing P4 HLIR"
rm -rf p4-hlir
git clone https://github.com/p4lang/p4-hlir.git p4-hlir
cd p4-hlir
python2.7 setup.py install

cd $env_dir/..

echo "Finished!"
