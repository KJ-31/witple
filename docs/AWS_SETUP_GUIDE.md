# GitHub Actions + EKS CI/CD 설정 가이드

테라폼으로 관리하는 EKS 클러스터에 GitHub Actions로 자동 배포하는 설정 방법입니다.

## 🔐 **1단계: GitHub Secrets 설정**

### GitHub Repository → Settings → Secrets and variables → Actions

다음 시크릿들을 추가:

```bash
# AWS 계정 정보
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

## 🏗️ **2단계: 테라폼에서 필요한 리소스들**

### IAM Role for GitHub Actions
```hcl
# GitHub OIDC Provider 생성
resource "aws_iam_openid_connect_provider" "github_actions" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com",
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1"
  ]
}

# GitHub Actions용 IAM Role 생성
resource "aws_iam_role" "github_actions" {
  name = "github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:your-username/witple:*"
          }
        }
      }
    ]
  })
}

# ECR 권한
resource "aws_iam_role_policy_attachment" "github_actions_ecr" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser"
}

# EKS 권한
resource "aws_iam_role_policy_attachment" "github_actions_eks" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# 추가 권한
resource "aws_iam_role_policy" "github_actions_additional" {
  name = "github-actions-additional"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:UpdateKubeconfig",
          "eks:CreateAccessEntry",
          "eks:DescribeAccessEntry",
          "eks:ListAccessEntries",
          "eks:AssociateAccessPolicy",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeVpcs"
        ]
        Resource = "*"
      }
    ]
  })
}
```

### ECR Repositories
```hcl
# ECR 리포지토리 생성 - 백엔드
resource "aws_ecr_repository" "witple_backend" {
  name                 = "witple-backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ECR 리포지토리 생성 - 프론트엔드
resource "aws_ecr_repository" "witple_frontend" {
  name                 = "witple-frontend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}
```

### EKS Cluster 및 ALB Controller
```hcl
# EKS OIDC Provider 데이터
data "aws_eks_cluster" "witple_cluster" {
  name = "witple-cluster"
}

data "tls_certificate" "eks_cluster" {
  url = data.aws_eks_cluster.witple_cluster.identity[0].oidc[0].issuer
}

# EKS OIDC Provider 생성
resource "aws_iam_openid_connect_provider" "eks_cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks_cluster.certificates[0].sha1_fingerprint]
  url             = data.aws_eks_cluster.witple_cluster.identity[0].oidc[0].issuer
}

# ALB Controller IAM Role
resource "aws_iam_role" "aws_load_balancer_controller" {
  name = "aws-load-balancer-controller"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks_cluster.arn
        }
        Condition = {
          StringEquals = {
            "${replace(data.aws_eks_cluster.witple_cluster.identity[0].oidc[0].issuer, "https://", "")}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller"
            "${replace(data.aws_eks_cluster.witple_cluster.identity[0].oidc[0].issuer, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

# ALB Controller 정책 연결
resource "aws_iam_role_policy_attachment" "aws_load_balancer_controller" {
  role       = aws_iam_role.aws_load_balancer_controller.name
  policy_arn = "arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess"
}

# ALB Controller 추가 정책
resource "aws_iam_role_policy" "aws_load_balancer_controller" {
  name = "aws-load-balancer-controller-additional"
  role = aws_iam_role.aws_load_balancer_controller.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "iam:CreateServiceLinkedRole",
          "ec2:DescribeAccountAttributes",
          "ec2:DescribeAddresses",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeInstances",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeTags",
          "ec2:GetCoipPoolUsage",
          "ec2:DescribeCoipPools",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeLoadBalancerAttributes",
          "elasticloadbalancing:DescribeListeners",
          "elasticloadbalancing:DescribeListenerCertificates",
          "elasticloadbalancing:DescribeSSLPolicies",
          "elasticloadbalancing:DescribeRules",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeTargetGroupAttributes",
          "elasticloadbalancing:DescribeTargetHealth",
          "elasticloadbalancing:DescribeTags"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cognito-idp:DescribeUserPoolClient",
          "acm:ListCertificates",
          "acm:DescribeCertificate",
          "iam:ListServerCertificates",
          "iam:GetServerCertificate",
          "waf-regional:GetWebACL",
          "waf-regional:GetWebACLForResource",
          "waf-regional:AssociateWebACL",
          "waf-regional:DisassociateWebACL",
          "wafv2:GetWebACL",
          "wafv2:GetWebACLForResource",
          "wafv2:AssociateWebACL",
          "wafv2:DisassociateWebACL",
          "shield:DescribeProtection",
          "shield:GetSubscriptionState",
          "shield:DescribeSubscription",
          "shield:CreateProtection",
          "shield:DeleteProtection"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateSecurityGroup",
          "ec2:CreateTags"
        ]
        Resource = "arn:aws:ec2:*:*:security-group/*"
        Condition = {
          StringEquals = {
            "ec2:CreateAction" = "CreateSecurityGroup"
          }
          Null = {
            "aws:RequestTag/elbv2.k8s.aws/cluster" = "false"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateTags",
          "ec2:DeleteTags"
        ]
        Resource = "arn:aws:ec2:*:*:security-group/*"
        Condition = {
          Null = {
            "aws:RequestTag/elbv2.k8s.aws/cluster" = "true"
            "aws:ResourceTag/elbv2.k8s.aws/cluster" = "false"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:RevokeSecurityGroupIngress",
          "ec2:DeleteSecurityGroup"
        ]
        Resource = "*"
        Condition = {
          Null = {
            "aws:ResourceTag/elbv2.k8s.aws/cluster" = "false"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:CreateLoadBalancer",
          "elasticloadbalancing:CreateTargetGroup"
        ]
        Resource = "*"
        Condition = {
          Null = {
            "aws:RequestTag/elbv2.k8s.aws/cluster" = "false"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:CreateListener",
          "elasticloadbalancing:DeleteListener",
          "elasticloadbalancing:CreateRule",
          "elasticloadbalancing:DeleteRule"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:AddTags",
          "elasticloadbalancing:RemoveTags"
        ]
        Resource = [
          "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*",
          "arn:aws:elasticloadbalancing:*:*:loadbalancer/net/*/*",
          "arn:aws:elasticloadbalancing:*:*:loadbalancer/app/*/*"
        ]
        Condition = {
          Null = {
            "aws:RequestTag/elbv2.k8s.aws/cluster" = "true"
            "aws:ResourceTag/elbv2.k8s.aws/cluster" = "false"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:AddTags",
          "elasticloadbalancing:RemoveTags"
        ]
        Resource = [
          "arn:aws:elasticloadbalancing:*:*:listener/net/*/*/*",
          "arn:aws:elasticloadbalancing:*:*:listener/app/*/*/*",
          "arn:aws:elasticloadbalancing:*:*:listener-rule/net/*/*/*",
          "arn:aws:elasticloadbalancing:*:*:listener-rule/app/*/*/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:ModifyLoadBalancerAttributes",
          "elasticloadbalancing:SetIpAddressType",
          "elasticloadbalancing:SetSecurityGroups",
          "elasticloadbalancing:SetSubnets",
          "elasticloadbalancing:DeleteLoadBalancer",
          "elasticloadbalancing:ModifyTargetGroup",
          "elasticloadbalancing:ModifyTargetGroupAttributes",
          "elasticloadbalancing:DeleteTargetGroup"
        ]
        Resource = "*"
        Condition = {
          Null = {
            "aws:ResourceTag/elbv2.k8s.aws/cluster" = "false"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:RegisterTargets",
          "elasticloadbalancing:DeregisterTargets"
        ]
        Resource = "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*"
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:SetWebAcl",
          "elasticloadbalancing:ModifyListener",
          "elasticloadbalancing:AddListenerCertificates",
          "elasticloadbalancing:RemoveListenerCertificates",
          "elasticloadbalancing:ModifyRule"
        ]
        Resource = "*"
      }
    ]
  })
}
```

## 🚀 **3단계: 배포 테스트**

### 코드 푸시로 배포
```bash
# main 브랜치에 푸시
git add .
git commit -m "Initial EKS deployment setup"
git push origin main
```

### GitHub Actions 확인
1. GitHub Repository → Actions 탭
2. "CI/CD Pipeline - Backend" 또는 "CI/CD Pipeline - Frontend" 워크플로우 실행 확인
3. 각 단계별 로그 확인

## 📊 **4단계: 배포 상태 확인**

### EKS 클러스터에서 확인
```bash
# kubeconfig 업데이트
aws eks update-kubeconfig --name witple-cluster --region ap-northeast-2

# 네임스페이스 확인
kubectl get namespace witple

# 파드 상태 확인
kubectl get pods -n witple

# 서비스 확인
kubectl get services -n witple

# Ingress 확인
kubectl get ingress -n witple

# 로그 확인
kubectl logs -f deployment/witple-backend -n witple
kubectl logs -f deployment/witple-frontend -n witple
```

### ALB DNS 확인
```bash
# ALB DNS 이름 가져오기
ALB_DNS=$(kubectl get ingress witple-ingress -n witple -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "ALB DNS: $ALB_DNS"

# API 테스트
curl http://$ALB_DNS/health
```

## 🔧 **5단계: 환경별 설정**

### 개발 환경 (선택사항)
```bash
# develop 브랜치용 별도 워크플로우 생성 가능
# 네임스페이스: witple-dev
# 리플리카: 1개
# 리소스: 최소
```

### 프로덕션 환경
```bash
# main 브랜치용 (현재 설정)
# 네임스페이스: witple
# 리플리카: 2개 (HPA로 자동 스케일링)
# 리소스: 충분한 할당
```

## 🚨 **6단계: 문제 해결**

### 일반적인 문제들

1. **EKS Access Entry 오류**
   ```bash
   # EKS Access Entry 확인
   aws eks list-access-entries --cluster-name witple-cluster --region ap-northeast-2
   
   # 수동으로 Access Entry 생성
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

2. **ECR 권한 오류**
   ```bash
   # ECR 리포지토리 확인
   aws ecr describe-repositories --repository-names witple-backend
   aws ecr describe-repositories --repository-names witple-frontend
   
   # ECR 로그인 테스트
   aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.ap-northeast-2.amazonaws.com
   ```

3. **ALB Ingress Controller 오류**
   ```bash
   # ALB Ingress Controller 상태 확인
   kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
   
   # 로그 확인
   kubectl logs -f deployment/aws-load-balancer-controller -n kube-system
   ```

### 디버깅 명령어
```bash
# 파드 상세 정보
kubectl describe pod <pod-name> -n witple

# 이벤트 확인
kubectl get events -n witple --sort-by='.lastTimestamp'

# 네트워크 정책 확인
kubectl get networkpolicies -n witple

# ConfigMap 확인
kubectl get configmap app-config -n witple -o yaml

# Secret 확인
kubectl get secret db-secret -n witple -o yaml
kubectl get secret app-secret -n witple -o yaml
```

## 📈 **7단계: 모니터링 및 스케일링**

### HPA 상태 확인
```bash
# HPA 상태 확인
kubectl get hpa -n witple

# HPA 상세 정보
kubectl describe hpa witple-backend-hpa -n witple
kubectl describe hpa witple-frontend-hpa -n witple

# 리소스 사용량 확인
kubectl top pods -n witple
```

### 로그 모니터링
```bash
# 실시간 로그 확인
kubectl logs -f deployment/witple-backend -n witple
kubectl logs -f deployment/witple-frontend -n witple

# 특정 파드 로그 확인
kubectl logs <pod-name> -n witple
```

## 💰 **8단계: 비용 최적화**

### 리소스 최적화
```bash
# HPA 설정 조정
kubectl patch hpa witple-backend-hpa -n witple -p '{"spec":{"minReplicas":1,"maxReplicas":3}}'
kubectl patch hpa witple-frontend-hpa -n witple -p '{"spec":{"minReplicas":1,"maxReplicas":3}}'

# 리소스 요청/제한 조정
kubectl patch deployment witple-backend -n witple -p '{"spec":{"template":{"spec":{"containers":[{"name":"witple-backend","resources":{"requests":{"memory":"128Mi","cpu":"100m"},"limits":{"memory":"256Mi","cpu":"200m"}}}]}}}}'
```

---

**GitHub Actions + EKS CI/CD 설정 완료!** 🎉

이제 `git push origin main`으로 코드를 푸시하면 자동으로 EKS에 배포됩니다.
