#!/usr/bin/env python3
import requests
import datetime
import json
import sys
import argparse
import redis
from time import sleep
import os
import psutil
import signal
from pyVim.connect import SmartConnectNoSSL
from pyVmomi import vim, VmomiSupport
from datetime import datetime, timedelta
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class identity(object):
    def __init__(self, document=None):
        if document is None:
            # need to follow register.py process for data retrieval
            document = {}
        else:
            identity = document
        for k, v in identity.items():
            if isinstance(k, str):
                setattr(self, k, v)
            else:
                setattr(self, k.decode('utf-8'), v)

    def _get_url(self, url):
        response = requests.get(url)
        try:
            response.raise_for_status()
        except:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def __call__(self):
        return self.__dict__

class hosts_file(object):
    def __init__(self, ip_address, hostname, filename='/etc/hosts'):
        hosts = {}
        found = False
        with open(filename) as fh:
            original_hosts = fh.readlines()
        for line in original_hosts:
            try:
                (ip, name) = line.split()
                if hostname == name:
                    hosts[name] = ip_address
                else:
                    hosts[name] = ip
            except ValueError as err:
                pass
        if not found:
            hosts[hostname] = ip_address
        with open(filename, 'w') as fh:
            for k in hosts.keys():
                if isinstance(k, bytes):
                    k = k.decode()
                print('%s\t%s' % (hosts[k], k), file=fh)
        for pid in psutil.process_iter(['pid', 'name']):
            if pid.info['name'] == "dnsmasq":
                os.kill(pid.info['pid'], signal.SIGHUP)
                break

class vcenter_inventory():
    def __init__(self, session,vcenter_server):
        self.vcenter_server = vcenter_server
        self.session = session
        self.identity = {}
        self.vcenter_url = 'https://' + self.vcenter_server + '/rest'
        self.session.post(self.vcenter_url + '/com/vmware/cis/session')

    def collect(self,vm_id,id_prefix):
        self.vm_id = vm_id
        self.id_prefix = id_prefix
        network_check = self._get('/vcenter/vm/' + self.vm_id + '/guest/identity')
        status = network_check.status_code
        while status != 200:
            network_check = self._get('/vcenter/vm/' + self.vm_id + '/guest/identity')
            status = network_check.status_code
            sleep(5)
        self.identity.update(network_check.json()['value'])
        self.identity['vmId'] = self.vm_id
        self.identity['now'] = datetime.now().isoformat()
        self.tag_collection()
        return(self.identity)
    
    def _get(self, api_path):
        resp = self.session.get(self.vcenter_url + api_path)
        return(resp)

    #tag serialization
    def tag_collection(self):
        vcenter_url_vm_list_attached_tags = self.vcenter_url + "/com/vmware/cis/tagging/tag-association?~action=list-attached-tags"
        vm_obj = {"object_id": {"id": self.vm_id, "type": "VirtualMachine"}}
        resp = self.session.post(vcenter_url_vm_list_attached_tags, data=json.dumps(vm_obj),
                headers={
                    'content-type': 'application/json'
                })
        tags = resp.json()['value']
        vcenter_url_get_tag = self.vcenter_url + "/com/vmware/cis/tagging/tag/id:{}"
        vcenter_url_get_category = self.vcenter_url + "/com/vmware/cis/tagging/category/id:{}"
        for tag in tags:
            resp = self.session.get(vcenter_url_get_tag.format(tag))
            tag_value = resp.json()['value']['name']
            category_id = resp.json()['value']['category_id']
            resp = self.session.get(
                    vcenter_url_get_category.format(category_id))
            tag_name = resp.json()['value']['name']
            tag_name = tag_name.replace(self.id_prefix+'_', "")
            self.identity[tag_name] = tag_value

class redis_inventory():
    def __init__(self):
        self.redis = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

    def update_redis(self,id):
        self.identity = identity(id)
        old_identity = self.redis.hgetall(self.identity.Name)
        if old_identity:
            self.old_identity = identity(document=old_identity)
            self.redis.srem(self.old_identity.Lab_Group, self.old_identity.ip_address)
        self.redis.hmset(self.identity.Name, self.identity())
        self.redis.sadd(self.identity.Lab_Group, self.identity.ip_address)
        self.redis.sadd('groups', self.identity.Lab_Group)
        self.redis.sadd('names', self.identity.Name)

    def check_redis(self, vm_hostname):
        return(self.redis.hgetall(vm_hostname))
    
    def publish_redis(self,channel,pdata):
        self.redis.publish(channel,json.dumps({channel:pdata}))


parser = argparse.ArgumentParser()
parser.add_argument('--host', required=True)
parser.add_argument('--username', default='administrator@vsphere.local', required=True)
parser.add_argument('--password', required=True)
parser.add_argument('--id', required=True)
parser.add_argument('--method', default='collect')
parser.add_argument('--vm_name')
args = parser.parse_args()

#global vars
interval = 30
last_event_key = 0

#host vars
vcenter_host = args.host
vcenter_user = args.username
vcenter_password = args.password
id_name = args.id
client = SmartConnectNoSSL(host=vcenter_host,
                        user=vcenter_user,
                        pwd=vcenter_password)

#event collection vars
event_type_list = ['VmPoweredOnEvent','DrsVmPoweredOnEvent']

filter_spec = vim.event.EventFilterSpec(eventTypeId=event_type_list)
collect_events  = client.content.eventManager.CreateCollectorForEvents(filter=filter_spec)

#requests session vars
session = requests.Session()
session.verify = False
session.auth = (vcenter_user,vcenter_password)

if args.method == 'collect':
    try:
        while True:
            #loop through events
            for event in reversed(collect_events.latestPage):
                if last_event_key < event.key:
                    login = vcenter_inventory(session,vcenter_host)
                    folder = login._get('/vcenter/folder?filter.names=' + id_name).json()['value'][0]['folder']
                    vm_id = str(event.vm.vm).split(':')[1].replace('\'','')
                    check_vm = login._get('/vcenter/vm?filter.names=' + event.vm.name + '&filter.vms=' + vm_id  + '&filter.folders=' + folder)
                    check_vm_length = len(check_vm.json()['value'])
                    if check_vm_length != 0 and check_vm.status_code == 200:
                        if check_vm.json()['value'][0]['power_state'] == "POWERED_ON":
                            inv_collection = login.collect(check_vm.json()['value'][0]['vm'],id_name)
                            host_inv = redis_inventory()
                            in_redis = host_inv.check_redis(inv_collection['host_name'])
                            #execute when host not found in redis
                            if not bool(in_redis) and 'Lab_Name' in inv_collection.keys():
                                hosts_file(inv_collection['ip_address'], inv_collection['Lab_Name'])
                                host_inv.update_redis(inv_collection)
                                host_inv.publish_redis('bootstrap',inv_collection['Lab_Name'])
                    last_event_key = event.key
            sleep(float(interval))
    except KeyboardInterrupt:
        print('\nCaught keyboard interrupt, exiting ...')
    collect_events.DestroyCollector()
elif args.method == 'add' and args.vm_name:
    login = vcenter_inventory(session,vcenter_host)
    host_inv = redis_inventory()
    folder = login._get('/vcenter/folder?filter.names=' + id_name).json()['value'][0]['folder']
    check_vm = login._get('/vcenter/vm?filter.names=' + args.vm_name + '&filter.folders=' + folder)
    inv_collection = login.collect(check_vm.json()['value'][0]['vm'],id_name)
    hosts_file(inv_collection['ip_address'], inv_collection['Lab_Name'])
    host_inv.update_redis(inv_collection)
    host_inv.publish_redis('bootstrap',inv_collection['Lab_Name'])
else:
    print("Invalid Args Passed")