# GitHub Actions OIDC 설정 가이드

GitHub Actions에서 AWS EKS에 배포하기 위한 OIDC (OpenID Connect) 설정 방법을 안내합니다.

## 🔍 문제 상황

기존 AWS Access Key 방식 대신 더 안전한 OIDC 방식을 사용하여 GitHub Actions가 AWS 리소스에 접근할 수 있도록 설정합니다.

## 🛠️ 해결 방법

### 1단계: GitHub OIDC Provider 생성

AWS IAM에서 GitHub Actions용 OIDC provider를 생성합니다:

```bash
# GitHub OIDC Provider 생성
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --region ap-northeast-2
```

### 2단계: GitHub Actions IAM 정책 생성

```bash
# GitHub Actions용 IAM 정책 생성
cat > github-actions-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "eks:DescribeCluster",
        "eks:UpdateKubeconfig",
        "eks:CreateAccessEntry",
        "eks:DescribeAccessEntry",
        "eks:ListAccessEntries",
        "eks:DeleteAccessEntry",
        "eks:AssociateAccessPolicy",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeVpcs",
        "sts:AssumeRoleWithWebIdentity",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# 정책 생성
aws iam create-policy \
  --policy-name GitHubActionsPolicy \
  --policy-document file://github-actions-policy.json \
  --region ap-northeast-2
```

### 3단계: Trust Policy 수정

`trust-policy-github-actions.json` 파일에서 다음 부분을 수정:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_USERNAME/witple:*"
        }
      }
    }
  ]
}
```

**중요**: 
- `YOUR_AWS_ACCOUNT_ID`를 실제 AWS 계정 ID로 변경
- `YOUR_GITHUB_USERNAME`을 실제 GitHub 사용자명으로 변경

### 4단계: GitHub Actions IAM 역할 생성

```bash
# trust-policy-github-actions.json 파일 수정 후 실행
# GitHub Actions용 IAM 역할 생성
aws iam create-role \
  --role-name github-actions-role \
  --assume-role-policy-document file://trust-policy-github-actions.json \
  --region ap-northeast-2

# 정책 연결
aws iam attach-role-policy \
  --role-name github-actions-role \
  --policy-arn arn:aws:iam::YOUR_AWS_ACCOUNT_ID:policy/GitHubActionsPolicy \
  --region ap-northeast-2
```

### 5단계: AWS Load Balancer Controller IAM 역할 생성

```bash
# ALB Controller용 Trust Policy 생성
cat > trust-policy-alb-controller.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:oidc-provider/YOUR_EKS_CLUSTER_OIDC_ISSUER"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "YOUR_EKS_CLUSTER_OIDC_ISSUER:sub": "system:serviceaccount:kube-system:aws-load-balancer-controller",
          "YOUR_EKS_CLUSTER_OIDC_ISSUER:aud": "sts.amazonaws.com"
        }
      }
    }
  ]
}
EOF

# ALB Controller IAM 역할 생성
aws iam create-role \
  --role-name aws-load-balancer-controller \
  --assume-role-policy-document file://trust-policy-alb-controller.json

# ALB Controller 정책 연결
aws iam attach-role-policy \
  --role-name aws-load-balancer-controller \
  --policy-arn arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess

# ALB Controller 추가 정책 연결
curl -o iam_policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.5.4/docs/install/iam_policy.json

aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam_policy.json

aws iam attach-role-policy \
  --role-name aws-load-balancer-controller \
  --policy-arn arn:aws:iam::YOUR_AWS_ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy
```

### 6단계: GitHub Repository 설정

GitHub Repository의 Settings → Secrets and variables → Actions에서 다음 시크릿을 추가:

```bash
# 필수 시크릿
AWS_ACCOUNT_ID=YOUR_AWS_ACCOUNT_ID

# 애플리케이션 설정
SECRET_KEY=your-super-secret-key-for-production

# 데이터베이스 설정
DATABASE_URL=postgresql://witple_user:password@your-rds-endpoint:5432/witple
REDIS_URL=redis://your-redis-endpoint:6379

# 도메인 설정 (선택사항)
DOMAIN_NAME=yourdomain.com
CERTIFICATE_ARN=arn:aws:acm:ap-northeast-2:YOUR_AWS_ACCOUNT_ID:certificate/certificate-id
```

### 7단계: EKS Access Entry 설정

GitHub Actions 역할에 EKS 클러스터 접근 권한을 부여합니다:

```bash
# EKS Access Entry 생성
aws eks create-access-entry \
  --cluster-name witple-cluster \
  --region ap-northeast-2 \
  --principal-arn "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:role/github-actions-role" \
  --type STANDARD

# 클러스터 관리자 권한 부여
aws eks associate-access-policy \
  --cluster-name witple-cluster \
  --region ap-northeast-2 \
  --principal-arn "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:role/github-actions-role" \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster
```

## 🔧 현재 설정 확인

### OIDC Provider 확인
```bash
# GitHub OIDC Provider 확인
aws iam list-open-id-connect-providers

# 특정 Provider 상세 정보
aws iam get-open-id-connect-provider \
  --open-id-connect-provider-arn arn:aws:iam::YOUR_AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

### IAM 역할 확인
```bash
# GitHub Actions 역할 확인
aws iam get-role --role-name github-actions-role

# 역할에 연결된 정책 확인
aws iam list-attached-role-policies --role-name github-actions-role
```

### EKS Access Entry 확인
```bash
# EKS Access Entry 목록 확인
aws eks list-access-entries \
  --cluster-name witple-cluster \
  --region ap-northeast-2

# 특정 Access Entry 확인
aws eks describe-access-entry \
  --cluster-name witple-cluster \
  --region ap-northeast-2 \
  --principal-arn "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:role/github-actions-role"
```

## 🚨 문제 해결

### 1. OIDC Provider가 이미 존재하는 경우
```bash
# 기존 Provider 삭제 후 재생성
aws iam delete-open-id-connect-provider \
  --open-id-connect-provider-arn arn:aws:iam::YOUR_AWS_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```

### 2. IAM 역할이 이미 존재하는 경우
```bash
# 기존 정책 분리
aws iam detach-role-policy \
  --role-name github-actions-role \
  --policy-arn arn:aws:iam::YOUR_AWS_ACCOUNT_ID:policy/GitHubActionsPolicy

# 기존 역할 삭제 후 재생성
aws iam delete-role --role-name github-actions-role
```

### 3. EKS Access Entry가 이미 존재하는 경우
```bash
# 기존 Access Entry 삭제 후 재생성
aws eks delete-access-entry \
  --cluster-name witple-cluster \
  --region ap-northeast-2 \
  --principal-arn "arn:aws:iam::YOUR_AWS_ACCOUNT_ID:role/github-actions-role"
```

## ✅ 설정 완료 후 테스트

GitHub Actions 워크플로우가 성공적으로 실행되는지 확인:

1. GitHub Repository에 코드 푸시
2. Actions 탭에서 워크플로우 실행 상태 확인
3. "Configure AWS credentials" 단계에서 오류가 없는지 확인

---

**OIDC 설정 완료!** 🎉

이제 GitHub Actions에서 AWS EKS에 안전하게 배포할 수 있습니다.
