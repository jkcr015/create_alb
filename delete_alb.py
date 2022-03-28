import boto3

ec2 = boto3.resource('ec2')

vpc_client = boto3.client("ec2")

filters = [{'Name':'tag:Name', 'Values':['myasgn*']}]

vpcs = list(ec2.vpcs.filter(Filters=filters))

subnets = list(ec2.subnets.filter(Filters=filters))

instances = list(ec2.instances.filter(Filters=filters))


for inst in instances:
    print ('deleting instances ' + inst.id)
    instance = ec2.Instance(inst.id)
    instance.terminate()
    instance.wait_until_terminated()


paginator = vpc_client.get_paginator('describe_internet_gateways')
response_iterator = paginator.paginate(Filters=filters)
full_result = response_iterator.build_full_result()
internet_gateways_list = []
for page in full_result['InternetGateways']:
    internet_gateways_list.append(page)

paginator = vpc_client.get_paginator('describe_route_tables')
response_iterator = paginator.paginate(Filters=filters)
full_result = response_iterator.build_full_result()
rt_list = []
for page in full_result['RouteTables']:
    rt_list.append(page)

for rt in rt_list:
    print ('deleting ' + rt['RouteTableId'])
    #print(rt['Associations']['RouteTableAssociationId'])
    #print(rt['RouteTableAssociationId'])
    #route_table_association = ec2.RouteTableAssociation(rt['RouteTableId'])
    #response = route_table_association.delete(
    #            DryRun=False
    #            )
    #vpc_client.disassociate_route_table(AssociationId=rt['RouteTableAssociationId'])
    vpc_client.delete_route_table(RouteTableId=rt['RouteTableId'])
    #print (list(rt))

for igw in internet_gateways_list:
    for vpc in vpcs:
        print ('deleting ' + igw['InternetGatewayId'])
        vpc_client.detach_internet_gateway(
                InternetGatewayId=igw['InternetGatewayId'], VpcId=vpc.id)
        vpc_client.delete_internet_gateway(
                InternetGatewayId=igw['InternetGatewayId'])

for subnet in subnets:
    print ('deleting ' + subnet.id)
    vpc_client.delete_subnet(SubnetId=subnet.id)

for vpc in vpcs:
    print ('deleting ' + vpc.id)
    vpc_client.delete_vpc(VpcId=vpc.id)

