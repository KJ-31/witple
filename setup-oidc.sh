#!/bin/bash

# OIDC 설정 스크립트
# 사용법: ./setup-oidc.sh YOUR_AWS_ACCOUNT_ID

if [ -z "$1" ]; then
    echo "❌ AWS 계정 ID를 입력해주세요"
    echo "사용법: ./setup-oidc.sh YOUR_AWS_ACCOUNT_ID"
    exit 1
fi

AWS_ACCOUNT_ID=$1

echo "🚀 GitHub Actions OIDC 설정을 시작합니다..."
echo "📋 AWS 계정 ID: $AWS_ACCOUNT_ID"

# 1단계: OIDC Provider 생성
echo "🔑 1단계: OIDC Provider 생성 중..."
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --client-id-list sts.amazonaws.com 2>/dev/null || {
  echo "⚠️ OIDC Provider가 이미 존재하거나 생성에 실패했습니다"
}

# 2단계: Trust Policy 업데이트
echo "📝 2단계: Trust Policy 업데이트 중..."
sed "s/AWS_ACCOUNT_ID/$AWS_ACCOUNT_ID/g" trust-policy-github-actions.json > trust-policy-updated.json

# 3단계: IAM 역할 생성
echo "👤 3단계: GitHub Actions IAM 역할 생성 중..."
aws iam create-role \
  --role-name github-actions-role \
  --assume-role-policy-document file://trust-policy-updated.json || {
  echo "⚠️ 역할이 이미 존재합니다. Trust Policy를 업데이트합니다..."
  aws iam update-assume-role-policy \
    --role-name github-actions-role \
    --policy-document file://trust-policy-updated.json
}

# 4단계: 정책 연결
echo "🔐 4단계: 필요한 정책들을 연결 중..."

# EKS 관련 정책들
POLICIES=(
  "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy" 
  "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess"
  "arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess"
  "arn:aws:iam::aws:policy/AmazonEC2FullAccess"
  "arn:aws:iam::aws:policy/IAMReadOnlyAccess"
)

for policy in "${POLICIES[@]}"; do
  aws iam attach-role-policy \
    --role-name github-actions-role \
    --policy-arn $policy || echo "⚠️ 정책 $policy 연결 실패 또는 이미 연결됨"
done

# 5단계: 커스텀 정책 생성 및 연결
echo "📋 5단계: 커스텀 EKS 정책 생성 중..."
cat > eks-access-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "eks:*",
                "iam:PassRole",
                "iam:CreateServiceLinkedRole",
                "iam:ListRoles",
                "iam:ListRolePolicies",
                "iam:ListAttachedRolePolicies",
                "ec2:DescribeSecurityGroups",
                "ec2:DescribeSubnets",
                "ec2:DescribeVpcs",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams"
            ],
            "Resource": "*"
        }
    ]
}
EOF

aws iam create-policy \
  --policy-name GitHubActionsEKSPolicy \
  --policy-document file://eks-access-policy.json 2>/dev/null || echo "⚠️ 정책이 이미 존재합니다"

aws iam attach-role-policy \
  --role-name github-actions-role \
  --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/GitHubActionsEKSPolicy || echo "⚠️ 정책 연결 실패 또는 이미 연결됨"

# 6단계: AWS Load Balancer Controller 역할 생성
echo "🏗️ 6단계: AWS Load Balancer Controller 역할 생성 중..."
cat > alb-trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::$AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
            },
            "Action": "sts:AssumeRoleWithWebIdentity"
        }
    ]
}
EOF

aws iam create-role \
  --role-name aws-load-balancer-controller \
  --assume-role-policy-document file://alb-trust-policy.json 2>/dev/null || echo "⚠️ ALB Controller 역할이 이미 존재합니다"

# ALB Controller 정책 다운로드 및 연결
curl -o alb-controller-policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.2/docs/install/iam_policy.json

aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://alb-controller-policy.json 2>/dev/null || echo "⚠️ ALB Controller 정책이 이미 존재합니다"

aws iam attach-role-policy \
  --role-name aws-load-balancer-controller \
  --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy || echo "⚠️ ALB Controller 정책 연결 실패 또는 이미 연결됨"

# 7단계: 정리
echo "🧹 7단계: 임시 파일 정리 중..."
rm -f trust-policy-updated.json eks-access-policy.json alb-trust-policy.json alb-controller-policy.json

echo ""
echo "✅ OIDC 설정이 완료되었습니다!"
echo ""
echo "📋 다음 단계:"
echo "1. GitHub 저장소 → Settings → Secrets and variables → Actions에서 다음 Secrets를 설정하세요:"
echo "   - AWS_ACCOUNT_ID: $AWS_ACCOUNT_ID"
echo "   - SECRET_KEY: (백엔드용 시크릿 키)"
echo "   - DATABASE_URL: (PostgreSQL 연결 문자열)"
echo "   - REDIS_URL: (Redis 연결 문자열)"
echo ""
echo "2. EKS 클러스터가 존재하는지 확인하세요:"
echo "   aws eks describe-cluster --name witple-cluster --region ap-northeast-2"
echo ""
echo "3. GitHub Actions가 재실행될 것입니다!"
echo ""
echo "🎉 설정 완료!"
