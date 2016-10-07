Ansible NCLU Demo
=======================

Quickstart: Run the demo
------------------------

    git clone https://github.com/cumulusnetworks/cldemo-vagrant
    cd cldemo-vagrant
    vagrant up oob-mgmt-server oob-mgmt-switch leaf01 leaf02 spine01 spine02 server01 server02
    vagrant ssh oob-mgmt-server
    sudo su - cumulus
    sudo apt-get install software-properties-common -y
    sudo apt-add-repository ppa:ansible/ansible -y
    sudo apt-get update
    sudo apt-get install ansible -qy
    git clone https://github.com/cumulusnetworks/cldemo-nclu-ansible
    cd cldemo-nclu-ansible
    ansible-playbook run-demo.yml
    ssh server01
    wget 172.16.2.101
    cat index.html
