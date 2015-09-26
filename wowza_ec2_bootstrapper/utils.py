import boto3

def get_is_vpc(inst_id, ec2=None):
    if ec2 is None:
        ec2 = boto3.client('ec2')
    data = ec2.describe_instances(InstanceIds=[inst_id])
    vpc_id = data.get('VpcId')
    return vpc_id is not None
