import sys
import os
import requests
import kubernetes
import json
from kubernetes.stream import stream
from pprint import pprint
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import base64
import jsonpatch
import copy

from flask import Flask, request, jsonify
import logging


webhook = Flask(__name__)
webhook.logger.setLevel(logging.INFO)

def admission_response(allowed, uid, patch):
    # return jsonify({"apiVersion": "admission.k8s.io/v1",
    #                 "kind": "AdmissionReview",
    #                 "response":
    #                     {"allowed": allowed,
    #                      "uid": uid,
    #                      "patchType": "JSONPatch",
    #                      "patch": patch                         
    #                      }
    #                 })
    response = jsonify({
                    "apiVersion": "admission.k8s.io/v1",
                    "kind": "AdmissionReview",
                    "response":
                        {
                            "allowed": allowed,
                            "uid": uid,
                            "patchType": "JSONPatch",
                            "patch": base64.b64encode(str(patch).encode()).decode()                         
                         }
                    })
    webhook.logger.warn(f"Final Response : {response}")    
    return response


@webhook.route('/mutate', methods=['POST'])
def handle_mutate_request():
    request_info = request.get_json()
    webhook.logger.warn(f"Mutating Webhook for pvc creation request received : {request_info}")
    return mutate_request(request_info)

def mutate_request(request_info):        
        uid = request_info["request"].get("uid")
        i_request = request_info["request"]

        pvc = i_request["object"]        
        modified_pvc = copy.deepcopy(pvc)
        
        pvc_name = pvc["metadata"]["name"]
        pvc_namespace = pvc["metadata"]["namespace"]
        webhook.logger.info(f"Mutating Webhook for pod : {pvc_name} in {pvc_namespace} namespace")

        # if CHECK_LABEL_KEY not in pvc["metadata"]["labels"]:
        #     webhook.logger.info(f"Pod does not have label with key type, skipping check")
        #     return admission_response(True, uid, f"Pod does not have label with key type, skipping admission check")

        tokenFile = "k8s-security/token"
        caFile = "k8s-security/ca.crt"

        if os.path.exists( tokenFile ) :
            token_file = open( tokenFile )
            aToken = token_file.readline().rstrip()
        else :
            webhook.logger.error(f"Error: Token File - %s doesn't exists. Aborting Connection - {tokenFile}")
            sys.exit(1)

        if os.path.exists( caFile ) :
            ca_File = open( caFile )
            aCertFile = ca_File.readline().rstrip()
        else :
            webhook.logger.error(f"Error: Cert File - %s doesn't exists. Aborting Connection - {caFile}")
            sys.exit(1)

        aConfiguration = client.Configuration()
        aConfiguration.host = os.environ.get('KUBE_API_SERVER', "https://localhost:443")
        aConfiguration.verify_ssl = False

        aConfiguration.api_key = {"authorization": "Bearer " + aToken}
        aApiClient = client.ApiClient(aConfiguration)
        v1 = client.CoreV1Api(aApiClient)        

        try:
            api_response = v1.read_namespaced_config_map("storageclass-config-cm", pvc_namespace )
            webhook.logger.warn(f"PVC Selector (from config map) :  {api_response.data['pvcselector']}")
            webhook.logger.warn(f"Storage Class names (from config map) :  {api_response.data['storageclassnames']}")
            PVC_SELECTOR=str(api_response.data['pvcselector'])
            STORAGE_CLASS_NAMES = str(api_response.data['storageclassnames'])
            assigned_sc_for_pvc=get_existing_storage_class(pvc, pvc_name)        
            config_val=PVC_SELECTOR.split("=")   
            if(len(config_val) !=2):
                webhook.logger.error(f"PVC Selector in config map is not in valid format. Must be key=value format, configured value : {PVC_SELECTOR}")
            else:
                label_key=config_val[0]
                label_value=config_val[1]
                try:
                    labels = pvc["metadata"]["labels"]
                    #skip the pods which does not have the labels
                    if label_key in labels.keys() and labels[label_key].lower() == label_value:
                        webhook.logger.warn(f"PVC with configured selector is being created, need to mutate the storage class here.")
                        tokens=pvc_name.split("-")
                        if len(tokens)<2:
                            webhook.logger.warn(f"Could not identify the PVC name for manipulation.")
                        else:
                            ordinal_no = int(tokens[-1])
                            webhook.logger.warn(f"Ordinal number for PVC is {ordinal_no}")
                            sc_names_for_pvc=STORAGE_CLASS_NAMES.split(",")
                            if len(sc_names_for_pvc) >= ordinal_no:
                                final_sc_name= sc_names_for_pvc[ordinal_no].strip() #"-".join((STORAGE_CLASS_PREFIX,ordinal_no))
                                modified_pvc=set_storage_class_for_pvc(modified_pvc,final_sc_name)
                            else:
                                webhook.logger.error(f"Not enough values provided for the given {ordinal_no}, falling to default storage class value")
                            #patchRespnose="[{'op': 'replace', 'path': '/spec/storageClassName', 'value':'" + final_pvc_name + "' }]"                    
                except ApiException as e:
                    webhook.logger.error("Exception while getting pod label : %s\n {e}")
                    sys.exit(1)

        except ApiException as e:
            obj = json.loads(e.body)
            webhook.logger.error(f"Exception while calling CoreV1Api->read_namespaced_config_map: %s\n {e}")
            sys.exit(1)
        #response=f"{'uid': {uid},'allowed': True,'patchType': 'JSONPatch','patch': [{'op': 'add', 'path': '/metadata/annotations/my-annotation', 'value': 'true'}]}"
        #webhook.logger.warn(f"Mutating Webhook for pod creation response prepared : {patchRespnose}")
        patch = jsonpatch.JsonPatch.from_diff(pvc, modified_pvc)
        webhook.logger.warn(f"Mutating Webhook for pod creation response prepared : {patch}")
        return admission_response(True, uid,  patch)

def set_storage_class_for_pvc(pvc,sc_name):    
    pvc['spec']['storageClassName'] = sc_name
    webhook.logger.warn(f"PVC with new storage class :  {pvc}")
    return pvc

def get_existing_storage_class(pvc, pvc_name):
    existing_sc = ""
    if "storageClassName" in pvc["spec"]:
        webhook.logger.warn(f"Existing storage class on PVC:  {pvc['spec']['storageClassName']}")
        existing_sc = pvc['spec']['storageClassName']
    else:
        webhook.logger.warn(f"No storage class provided in PVC : {pvc_name}")
    return existing_sc



# if __name__ == '__main__':
#     webhook.run(host='0.0.0.0', port=5005)