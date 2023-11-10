# intelligent-storage-class-k8s

Sample mutate webhook implemenation that can mutate the PVC creation requests for storage class changes based on the PVC ordinal number.

## Getting started

This contains the steps and code that can be used to create and apply(mutate) PVC creation with intelligent storage classes. Important point is here the pods are not indepedently created but are managed as part of STS controller.

## How it works?

- The decision of accepting or skipping the mutation of the request is for all the PVC CREATE request in the namepsace provided.
- The admission controller upon receving the request, reads the pvc creation request and checks if the selector label is available or not.
- Then it reads the configuration map in the same namespace(configmap=storageclass-config-cm) with fixed key/value(volume=resilient-volumes).
- If the PVC being created has the label mentioned above, then it would read the key "storageclassnames" in the same config-map and splits the value with ",". The storage  classes after the split are given to each ordinal number pvc.For example, "storageclassnames": "first-fd-sc, second-fd-sc"  configuration value, would provide "first-fd-sc" for the pvcs that has ordial number 0(e.g. pvc-data-0) and "second-fd-sc" would be storage class for the pod with ordinal number 1(e.g. pvc-data-1) etc.

## How to Deploy?
- Run and created objects provided in manifests folder.
- Capture the token and get the certificate.
```
  openssl genrsa -out rootca.key 2048
  openssl req -x509 -sha256 -new -nodes -key  rootca.key  -days 3650 -out rootca.crt ## here make sure to provide the details that matches req.conf values. 
  openssl req -x509 -nodes -days 730 -newkey rsa:2048 -keyout security/webhook.key -out security/webhook.crt -config security/req.conf -extensions 'v3_req' -CA security/rootca.crt -CAkey security/rootca.key

```

Before creating webhook-manifests, make sure to update webhook.crt, webhook.key in the webhook-secret.yaml in the webhook-manifests folder.
Also provide the clientConfig.caBundle in the webhook-mutate-config.yaml before creation of webhook configuration.

```

  kubectl -n default create -f webhook-manifests/
  kubectl -n default get secret pod-checker-secret -o yaml -o jsonpath='{.data.token}' | base64 -d > security/token
  kubectl -n default get secret pod-checker-secret -o yaml -o jsonpath='{.data.ca\.crt}' | base64 -d > security/ca.crt 
```

To check the working, use the manifests in the "tests" folder.

