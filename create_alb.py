########################################################################################
#
# APPLICATION LOAD BALANCER STEPS 
#
# 1. Create VPC.
#
# 2. Create 2 public subnets and 3 private subnets.
#
# 3. Create internet gateway and attach it to vpc created.
#
# 4. Create public route table and attach public subnets to it.
#
# 5. Create private route table and attach private subnets to it.
#
# 6. Attach interet gateway to public route table.
#
# 7. Attach NAT gateway to private route table.
#
# 8. Create security group for instances and add ingress rule.
#
# 9. Create security group for ALB and add ingress rule.
#
# 10. Create application load balancer.
#
# 11. Create target group and listener.
#
# 12. Attach targets to target group
#
########################################################################################
import boto3

from botocore.exceptions import ClientError


vpc_resource = boto3.resource('ec2')
vpc_client = boto3.client("ec2")
elb_client = boto3.client('elbv2')


def create_custom_vpc(ip_cidr):
    try:
        response = vpc_resource.create_vpc(CidrBlock=ip_cidr,
                                            InstanceTenancy='default',
                                            TagSpecifications=[{                                                                                                                                              'ResourceType':
                                                'vpc',
                                                'Tags': [{
                                                    'Key':
                                                    'Name',
                                                    'Value':
                                                    'myasgn_vpc'
                                                }]
                                            }])

    except ClientError:
        print('Could not create a vpc.')
        raise
    else:
        response.wait_until_available()
        return response


def create_custom_subnet(az, vpc_id, cidr_block):
    try:
        response = vpc_resource.create_subnet(TagSpecifications=[
            {
                'ResourceType': 'subnet',
                'Tags': [{
                    'Key': 'Name',
                    'Value': 'myasgn_' + cidr_block
                }]
            },
        ],
                                              AvailabilityZone=az,
                                              VpcId=vpc_id,
                                              CidrBlock=cidr_block)
    except ClientError:
        logger.exception(f'Could not create a custom subnet.')
        raise
    else:
        return response


def create_igw():
    try:
        response = vpc_resource.create_internet_gateway(TagSpecifications=[
            {
                'ResourceType': 'internet-gateway',
                'Tags': [{
                    'Key': 'Name',
                    'Value': 'myasgn_igw'
                }]
            },
        ])

    except ClientError:
        logger.exception('Could not create the internet gateway.')
        raise
    else:
        return response


def attach_igw_to_vpc(internet_gateway_id, vpc_id):
    try:
        response = vpc_client.attach_internet_gateway (
                InternetGatewayId=internet_gateway_id, VpcId=vpc_id)
    except ClientError:
        print('Could not attach an internet gateway to a VPC.')
        raise
    else:
        return response

def create_rt(vpc_id,var):
    try:
        response = vpc_client.create_route_table(
                VpcId=vpc_id,
                TagSpecifications=[
                    {
                        'ResourceType': 'route-table',
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': 'myasgn_' + var
                            },
                        ]
                    },
                ])
    except ClientError:
        print('Could not create the route table.')
        raise
    else:
        return response


def associate_route_table(route_table_id, subnet_id):
    try:
        for sbtid in subnet_id:
            response = vpc_client.associate_route_table(
                    RouteTableId=route_table_id, SubnetId=sbtid.id)
    except ClientError:
        print('Could not associate the route table with the subnet.')
        raise
    else:
        return response

def create_route(destination_cidr_block, gateway_id, route_table_id):
    try:
        response = vpc_client.create_route(
                DestinationCidrBlock=destination_cidr_block,
                GatewayId=gateway_id,
                RouteTableId=route_table_id)
    except ClientError:
        print('Could not create the route.')
        raise
    else:
        return response


def create_security_group(description, groupname, vpc_id):
    try:
        response = vpc_resource.create_security_group(Description=description,
                GroupName=groupname,
                VpcId=vpc_id,
                TagSpecifications=[{
                    'ResourceType': 'security-group',
                    'Tags': [{
                        'Key': 'Name',
                        'Value': groupname
                    }]
                }])
    except ClientError:
        print('Could not create a security group.')
        raise
    else:
        return response


def security_group_ingress(scrty_group_ec2, scrty_group_alb):
    try:
        response = vpc_client.authorize_security_group_ingress(
                GroupId=scrty_group_ec2,
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 80,
                        'ToPort': 80,
                        'UserIdGroupPairs': [{ 'GroupId': scrty_group_alb }] }
                ],)
    except ClientError:
        print('Could not authorize security group ingress')
        raise
    else:
        return response



def create_ingress_rule(scrty_group_alb):
    try:
        response = vpc_client.authorize_security_group_ingress(
                GroupId=scrty_group_alb,
                IpPermissions=[{
                        'IpProtocol': 'tcp',
                        'FromPort': 80,
                        'ToPort': 80,
                        'IpRanges': [{
                            'CidrIp': '0.0.0.0/0'
                        }]
                }])
    except ClientError:
        print('Could not authorize security group ingress')
        raise
    else:
        return response


def create_nat(subnet_id):
    try:
        # allocate IPV4 address for NAT gateway
        public_ip_allocation_id = vpc_client.allocate_address(Domain='vpc')

        # create NAT gateway
        response = vpc_client.create_nat_gateway(
                AllocationId=public_ip_allocation_id['AllocationId'],
                SubnetId=subnet_id,
                TagSpecifications=[{
                    'ResourceType': 'natgateway',
                    'Tags': [{
                        'Key': 'Name',
                        'Value': 'myasgn-natgw'
                        }]
                }])
        nat_gateway_id = response['NatGateway']['NatGatewayId']

        # wait until the NAT gateway is available
        waiter = vpc_client.get_waiter('nat_gateway_available')
        waiter.wait(NatGatewayIds=[nat_gateway_id])

    except ClientError:
        print('Could not create the NAT gateway.')
        raise
    else:
        return response


def create_instance(vpcid, subnetid, sg_id, var):
    AMI_ID = 'ami-0c02fb55956c7d316'
    user_data = '''
        #!/bin/bash
        sudo yum install httpd -y
        sudo systemctl enable httpd
        sudo echo "This is instance %s" > /var/www/html/index.html
        sudo systemctl start httpd''' % var
    try:
        response = vpc_resource.create_instances (
                SubnetId=subnetid,
                MinCount = 1,
                MaxCount = 1,
                ImageId=AMI_ID,
                SecurityGroupIds=[sg_id,],
                InstanceType='t2.micro',
                KeyName='trfm',
                UserData=user_data,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {
                                'Key': 'Name',
                                'Value': 'myasgn_'+var
                            },
                        ]
                    },
                ])
    except ClientError:
        print('Could not create the instance')
        raise
    else:
        return response

def create_load_balancer(subnetId, security_group):
    try:
        response = elb_client.create_load_balancer (
                Name='myasgn-lb',
                Subnets=subnetId,
                SecurityGroups=[security_group],
                Scheme='internet-facing',
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': 'myasgn_alb'
                    },
                ],)
    except ClientError:
        print('Could not create the load balancer')
        raise
    else:
        return response

def create_target_group(vpcid):
    try:
        response = elb_client.create_target_group(
                Name='myasgn-tg',
                Protocol='HTTP',
                Port=80,
                VpcId=vpcid)
    except ClientError:
        print('Could not create the target group')
        raise
    else:
        return response


def create_listener(alb_arn, tg_arn):
    try:
        response = elb_client.create_listener(
                DefaultActions=[
                    {
                        'TargetGroupArn': tg_arn,
                        'Type': 'forward',
                    },
                ],
                LoadBalancerArn=alb_arn,
                Port=80,
                Protocol='HTTP',)
    except ClientError:
        print('Could not create the target group')
        raise
    else:
        return response

def register_targets(tg_arn, targets_list):
    try:
        response = elb_client.register_targets(
                TargetGroupArn=tg_arn,
                Targets=targets_list)
    except ClientError:
        print('Could not register targets')
        raise
    else:
        return response

if __name__ == '__main__':

    #create vpc
    IP_CIDR = '10.0.0.0/16'
    DESTINATION_CIDR_BLOCK = '0.0.0.0/0'
    print(f'Creating a VPC...')

    vpc = create_custom_vpc(IP_CIDR)

    #create public subnets
    print('Creating first public subnet...')
    PUBLIC_CIDR_BLOCK_1 = '10.0.0.0/24'
    AZ_01 = 'us-east-1a'
    subnet_01 = create_custom_subnet(AZ_01, vpc.id, PUBLIC_CIDR_BLOCK_1)

    print('Creating second public subnet')
    PUBLIC_CIDR_BLOCK_2 = '10.0.1.0/24'
    AZ_02 = 'us-east-1b'
    subnet_02 = create_custom_subnet(AZ_02, vpc.id, PUBLIC_CIDR_BLOCK_2)

    #create private subnets
    print('Creating first private subnet')
    PRIVATE_CIDR_BLOCK_1 = '10.0.2.0/24'
    AZ_03 = 'us-east-1a'
    subnet_03 = create_custom_subnet(AZ_03, vpc.id, PRIVATE_CIDR_BLOCK_1)

    print('Creating second private subnet')
    PRIVATE_CIDR_BLOCK_2 = '10.0.3.0/24'
    AZ_04 = 'us-east-1b'
    subnet_04 = create_custom_subnet(AZ_04, vpc.id, PRIVATE_CIDR_BLOCK_2)

    print('Creating third private subnet')
    PRIVATE_CIDR_BLOCK_3 = '10.0.4.0/24'
    AZ_05 = 'us-east-1c'
    subnet_05 = create_custom_subnet(AZ_05, vpc.id, PRIVATE_CIDR_BLOCK_3)

    #create internet gateway
    print('Creating internet gateway')
    igw = create_igw()

    #Attach internet gateway to vpc
    print('Attaching internet gateway to vpc')
    igw_vpc = attach_igw_to_vpc(igw.id, vpc.id)

    #create route table for public and private subnets
    print('Creating public route table...')
    public_rt = create_rt(vpc.id,'PUBLIC_RT')

    #Associate public subnets to route table
    print('Attaching public subnets to the public route table...')
    pub_sbt = [subnet_01, subnet_02]
    associate_route_table(public_rt['RouteTable']['RouteTableId'], pub_sbt)

    #Attach internet gateway to the public route table
    print('Attaching igw route  to the public route table...')
    pub_route = create_route(DESTINATION_CIDR_BLOCK, igw.id, public_rt['RouteTable']['RouteTableId'])

    #Create private route table
    print('Creating private route table...')
    private_rt = create_rt(vpc.id,'PRIVATE_RT')

    #Associate private subnets to route table
    print('Attaching private subnets to the private route table...')
    prv_sbt = [subnet_03, subnet_04, subnet_05]
    associate_route_table(private_rt['RouteTable']['RouteTableId'], prv_sbt)

    #Create NAT Gateway for private subnet instances
    print('Create NAT gateway for private subnet instances')
    nat = create_nat(subnet_01.id)

    #Attach nat gateway to the private route table
    print('Attaching nat gateway to the private route table...')
    prv_route = create_route(
            DESTINATION_CIDR_BLOCK, 
            nat['NatGateway']['NatGatewayId'], 
            private_rt['RouteTable']['RouteTableId'])

    #Create security group for instances
    print('Creating security group for instances...')
    DESCRIPTION = 'Security group created for instances in application load balancer'
    GROUPNAME = 'myasgn_ec2_security-group'
    scrty_group_ec2 = create_security_group(DESCRIPTION, GROUPNAME, vpc.id)

    #Create instances in private subnets
    instance_01 = create_instance (vpc.id, subnet_03.id, scrty_group_ec2.id, 'ec2_01')

    instance_02 = create_instance (vpc.id, subnet_04.id, scrty_group_ec2.id, 'ec2_02')

    instance_03 = create_instance (vpc.id, subnet_05.id, scrty_group_ec2.id, 'ec2_03')

    #Create security group for load balancer
    print('Creating security group for load balancer...')
    DESCRIPTION = 'Security group created application load balancer'
    GROUPNAME = 'myasgn_alb_security-group'
    scrty_group_alb = create_security_group(DESCRIPTION, GROUPNAME, vpc.id)
  
    #Add ingress rule to application load balancer security group
    print('Add ingress rule to application load balancer security group')
    ing_alb_sg = create_ingress_rule(scrty_group_alb.id)

    #Add ingress rule to instance security group
    print('Adding ingress rule to instance security group')
    ing_sg = security_group_ingress(scrty_group_ec2.id, scrty_group_alb.id)


    #Create application load balancer
    print("Creating application load balancer")
    pub_sbt_id = [subnet_03.id, subnet_04.id, subnet_05.id]
    alb = create_load_balancer(pub_sbt_id, scrty_group_alb.id)

    #print(alb['LoadBalancers'][0]['LoadBalancerArn'])
    alb_arn = alb['LoadBalancers'][0]['LoadBalancerArn']

    #Create target group
    print('Creating target group...')
    tg = create_target_group(vpc.id)


    #print (tg['TargetGroups'][0]['TargetGroupArn'])
    tg_arn = tg['TargetGroups'][0]['TargetGroupArn']

    #Create listener
    print('Creating Listener...')
    lsn = create_listener(alb_arn,tg_arn)

    targetIds = [instance_01[0].id, instance_02[0].id, instance_03[0].id]

    #Wait until instances are running
    print('Wait until instances are running')
    for inst in targetIds:
        instance = vpc_resource.Instance(id=inst)
        instance.wait_until_running()
    
    targets_list = [dict(Id=target_id, Port=80) for target_id in targetIds]

    #Register instances to target group
    print("Register targets to target groups..")
    r_tg = register_targets(tg_arn, targets_list)
