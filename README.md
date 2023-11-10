# intelligent-storage-class-k8s



## Getting started

This contains the steps and code that can be used to create and apply(mutate) PVC creation with intelligent storage classes. Important point is here the pods are not indepedently created but are managed as part of STS controller.

## Add your files

## Steps
1. Create RootCA

openssl genrsa -out rootca.key 2048
openssl req -x509 -sha256 -new -nodes -key  rootca.key  -days 3650 -out rootca.crt  #Fill in the details here that would be used to create server certificate later, so must save it. <-- This details must match the details provided in req.conf file for certificate generation, below

2. Create server certificates
openssl req -x509 -nodes -days 730 -newkey rsa:2048 -keyout security/webhook.key -out security/webhook.crt -config security/req.conf -extensions 'v3_req' -CA security/rootca.crt -CAkey security/rootca.key


## Integrate with your tools
