import socket
import boto3

from wowza_ec2_bootstrapper.utils import get_is_vpc
from wowza_ec2_bootstrapper.actions import BaseAction

def address_from_url(url):
    return socket.gethostbyname(url)
    
def is_ipv4(address):
    try:
        socket.inet_aton(address)
    except socket.error:
        return False
    return True
    
class AssociateEIP(BaseAction):
    action_fields = dict(
        address={
            'required':['address', 'allocation_id'], 
            'help':'Either an IPv4 IP address or a hostname that can be used to retrieve it', 
        }, 
        allocation_id={
            'required':['address', 'allocation_id'], 
            'help':'The allocation_id of the Elastic IP', 
        }, 
    )
    def do_action(self, **kwargs):
        ec2 = boto3.client('ec2')
        inst_id = self.config.instance_metadata.instance_id
        address = kwargs.get('address')
        allocation_id = kwargs.get('allocation_id')
        is_vpc = self.config.get('is_vpc')
        if is_vpc is None:
            is_vpc = get_is_vpc(inst_id, ec2)
            self.config.is_vpc = is_vpc
        if is_vpc:
            if allocation_id is None:
                address = self.get_ipv4_address(address)
                data = ec2.describe_addresses()
                for addr_data in data['Addresses']:
                    if addr_data['PublicIp'] != address:
                        continue
                    allocation_id = addr_data['AllocationId']
                    break
            ec2.associate_address(InstanceId=inst_id, AllocationId=allocation_id)
            return True
        else:
            address = self.get_ipv4_address(address)
            ec2.associate_address(InstanceId=inst_id, PublicIp=address)
            return True
    def get_ipv4_address(self, address):
        if not is_ipv4(address):
            address = address_from_url(address)
        return address
