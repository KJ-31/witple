#!/bin/bash
"""
AWS Batch Processor 배포 스크립트
ECR에 Docker 이미지를 빌드/푸시하고 Batch Job Definition 생성
"""

set -e

# 환경 변수 설정
AWS_REGION=${AWS_REGION:-ap-northeast-2}
ECR_REPOSITORY="witple-batch-processor"
IMAGE_TAG=${IMAGE_TAG:-latest}
JOB_DEFINITION_NAME="witple-vectorization-job"
JOB_QUEUE_NAME="witple-fargate-queue"

# AWS 계정 ID 가져오기
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
FULL_IMAGE_URI="${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

echo "🚀 Starting AWS Batch Processor deployment"
echo "   AWS Region: ${AWS_REGION}"
echo "   ECR Repository: ${ECR_REPOSITORY}"
echo "   Image Tag: ${IMAGE_TAG}"
echo "   Full Image URI: ${FULL_IMAGE_URI}"

# 1. ECR 로그인
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}

# 2. ECR 리포지토리 확인/생성
echo "📦 Checking ECR repository..."
if ! aws ecr describe-repositories --repository-names ${ECR_REPOSITORY} --region ${AWS_REGION} > /dev/null 2>&1; then
    echo "📦 Creating ECR repository: ${ECR_REPOSITORY}"
    aws ecr create-repository \
        --repository-name ${ECR_REPOSITORY} \
        --region ${AWS_REGION} \
        --image-scanning-configuration scanOnPush=true
else
    echo "✅ ECR repository already exists: ${ECR_REPOSITORY}"
fi

# 3. Docker 이미지 빌드
echo "🏗️  Building Docker image..."
docker build -t ${ECR_REPOSITORY}:${IMAGE_TAG} .

# 4. 이미지 태그 지정
echo "🏷️  Tagging Docker image..."
docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${FULL_IMAGE_URI}

# 5. ECR에 푸시
echo "📤 Pushing image to ECR..."
docker push ${FULL_IMAGE_URI}

# 6. Job Definition 생성/업데이트
echo "📋 Creating/updating Batch Job Definition..."

# Job Definition JSON 생성
cat > job-definition.json << EOF
{
    "jobDefinitionName": "${JOB_DEFINITION_NAME}",
    "type": "container",
    "platformCapabilities": ["FARGATE"],
    "containerProperties": {
        "image": "${FULL_IMAGE_URI}",
        "vcpus": 2,
        "memory": 4096,
        "networkConfiguration": {
            "assignPublicIp": "ENABLED"
        },
        "fargatePlatformConfiguration": {
            "platformVersion": "1.4.0"
        },
        "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/witple-batch-job-execution-role",
        "jobRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/witple-batch-job-execution-role",
        "environment": [
            {
                "name": "AWS_DEFAULT_REGION",
                "value": "${AWS_REGION}"
            },
            {
                "name": "S3_BUCKET",
                "value": "user-actions-data"
            },
            {
                "name": "S3_PREFIX",
                "value": "user-actions/"
            }
        ],
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": "/aws/batch/job",
                "awslogs-region": "${AWS_REGION}",
                "awslogs-stream-prefix": "witple-batch"
            }
        }
    },
    "retryStrategy": {
        "attempts": 2
    },
    "timeout": {
        "attemptDurationSeconds": 3600
    }
}
EOF

# Job Definition 등록
aws batch register-job-definition \
    --cli-input-json file://job-definition.json \
    --region ${AWS_REGION}

echo "✅ Job Definition created/updated: ${JOB_DEFINITION_NAME}"

# 7. CloudWatch Log Group 생성 (존재하지 않는 경우)
echo "📊 Ensuring CloudWatch Log Group exists..."
if ! aws logs describe-log-groups --log-group-name-prefix "/aws/batch/job" --region ${AWS_REGION} | grep -q "/aws/batch/job"; then
    aws logs create-log-group \
        --log-group-name "/aws/batch/job" \
        --region ${AWS_REGION}
    echo "✅ CloudWatch Log Group created: /aws/batch/job"
else
    echo "✅ CloudWatch Log Group already exists: /aws/batch/job"
fi

# 8. 테스트 작업 제출 (옵션)
if [[ "${SUBMIT_TEST_JOB:-false}" == "true" ]]; then
    echo "🧪 Submitting test job..."
    
    TEST_JOB_NAME="witple-test-$(date +%s)"
    
    aws batch submit-job \
        --job-name ${TEST_JOB_NAME} \
        --job-queue ${JOB_QUEUE_NAME} \
        --job-definition ${JOB_DEFINITION_NAME} \
        --parameters inputBucket=user-actions-data,inputPrefix=user-actions/,maxRecords=100 \
        --region ${AWS_REGION}
    
    echo "✅ Test job submitted: ${TEST_JOB_NAME}"
fi

# 정리
rm -f job-definition.json

echo ""
echo "🎉 AWS Batch Processor deployment completed successfully!"
echo ""
echo "📋 Summary:"
echo "   - Docker image pushed to: ${FULL_IMAGE_URI}"
echo "   - Job Definition: ${JOB_DEFINITION_NAME}"
echo "   - Job Queue: ${JOB_QUEUE_NAME}"
echo ""
echo "🚀 To submit a job manually:"
echo "   aws batch submit-job \\"
echo "     --job-name witple-vectorization-\$(date +%s) \\"
echo "     --job-queue ${JOB_QUEUE_NAME} \\"
echo "     --job-definition ${JOB_DEFINITION_NAME} \\"
echo "     --parameters inputBucket=user-actions-data,inputPrefix=user-actions/"