#!/bin/bash

# ComfyUI AWS GPU Instance Launcher
# Usage: ./aws-launch.sh [region] [key-name]

set -e

REGION=${1:-us-east-1}
KEY_NAME=${2:-your-ec2-key}
INSTANCE_TYPE="g4dn.xlarge"
AMI_ID="ami-0c02fb55956c7d316"  # Deep Learning AMI Ubuntu 22.04
INSTANCE_NAME="ComfyUI-GPU-Test"

echo "🚀 Launching ComfyUI AWS GPU Instance"
echo "=================================="
echo "Region: $REGION"
echo "Instance Type: $INSTANCE_TYPE"
echo "Key Name: $KEY_NAME"
echo "AMI ID: $AMI_ID"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI not configured. Run 'aws configure' first."
    exit 1
fi

# Create security group if it doesn't exist
SG_NAME="comfyui-sg"
echo "🔒 Setting up security group..."

SG_ID=$(aws ec2 describe-security-groups --region $REGION --group-names $SG_NAME --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [ "$SG_ID" == "None" ]; then
    echo "Creating security group: $SG_NAME"
    SG_ID=$(aws ec2 create-security-group \
        --region $REGION \
        --group-name $SG_NAME \
        --description "ComfyUI Security Group" \
        --query 'GroupId' --output text)
    
    # Get your public IP
    MY_IP=$(curl -s ifconfig.me)/32
    echo "Your IP: $MY_IP"
    
    # Add rules
    aws ec2 authorize-security-group-ingress --region $REGION --group-id $SG_ID --protocol tcp --port 22 --cidr $MY_IP
    aws ec2 authorize-security-group-ingress --region $REGION --group-id $SG_ID --protocol tcp --port 7860 --cidr 0.0.0.0/0
    aws ec2 authorize-security-group-ingress --region $REGION --group-id $SG_ID --protocol tcp --port 8080 --cidr 0.0.0.0/0
    
    echo "✅ Security group created: $SG_ID"
else
    echo "✅ Using existing security group: $SG_ID"
fi

# Launch instance
echo "🚀 Launching EC2 instance..."

INSTANCE_ID=$(aws ec2 run-instances \
    --region $REGION \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $SG_ID \
    --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=50,VolumeType=gp3}' \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME},{Key=Project,Value=ComfyUI-Testing}]" \
    --query 'Instances[0].InstanceId' --output text)

echo "✅ Instance launched: $INSTANCE_ID"
echo "⏳ Waiting for instance to be running..."

aws ec2 wait instance-running --region $REGION --instance-ids $INSTANCE_ID

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --region $REGION \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

echo "✅ Instance is running!"
echo "🌐 Public IP: $PUBLIC_IP"
echo "💻 SSH Command: ssh -i ~/.ssh/$KEY_NAME.pem ubuntu@$PUBLIC_IP"
echo "🎨 ComfyUI will be at: http://$PUBLIC_IP:7860"

# Save instance info
cat > aws-instance-info.txt << EOF
Instance Information
===================
Instance ID: $INSTANCE_ID
Public IP: $PUBLIC_IP
Region: $REGION
Instance Type: $INSTANCE_TYPE
Key Name: $KEY_NAME
Security Group: $SG_ID

SSH Command:
ssh -i ~/.ssh/$KEY_NAME.pem ubuntu@$PUBLIC_IP

ComfyUI URL (after setup):
http://$PUBLIC_IP:7860

Upload files command:
scp -i ~/.ssh/$KEY_NAME.pem setup-aws-instance.sh docker-compose-aws.yaml aws-performance-test.py ubuntu@$PUBLIC_IP:~/

Terminate command:
aws ec2 terminate-instances --region $REGION --instance-ids $INSTANCE_ID
EOF

echo ""
echo "📋 Instance info saved to: aws-instance-info.txt"
echo ""
echo "🚀 Next steps:"
echo "1. Wait 2-3 minutes for instance to fully boot"
echo "2. Upload files: scp -i ~/.ssh/$KEY_NAME.pem setup-aws-instance.sh docker-compose-aws.yaml aws-performance-test.py ubuntu@$PUBLIC_IP:~/"
echo "3. SSH and run setup: ssh -i ~/.ssh/$KEY_NAME.pem ubuntu@$PUBLIC_IP"
echo "4. Run: chmod +x setup-aws-instance.sh && ./setup-aws-instance.sh"
echo "5. Upload your Docker files and run: docker-compose -f docker-compose-aws.yaml up --build"
echo ""
echo "⚠️  Remember to terminate instance when done to avoid charges!"
echo "   aws ec2 terminate-instances --region $REGION --instance-ids $INSTANCE_ID"