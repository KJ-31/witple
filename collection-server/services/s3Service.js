const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');
const zlib = require('zlib');
const { promisify } = require('util');

const gzip = promisify(zlib.gzip);

class S3Service {
  constructor() {
    // AWS S3 클라이언트 설정
    this.s3 = new AWS.S3({
      region: process.env.AWS_REGION || 'ap-northeast-2',
      apiVersion: '2006-03-01',
      maxRetries: 3,
      retryDelayOptions: {
        customBackoff: function(retryCount) {
          return Math.pow(2, retryCount) * 100; // 지수 백오프
        }
      }
    });
    
    this.bucket = process.env.S3_EVENTS_BUCKET || 'user-actions-data';
    
    // S3 연결 테스트
    this.testConnection();
  }

  async testConnection() {
    try {
      await this.s3.headBucket({ Bucket: this.bucket }).promise();
      console.log(`✅ S3 connection successful: ${this.bucket}`);
    } catch (error) {
      console.error(`❌ S3 connection failed: ${error.message}`);
      console.error('Please check AWS credentials and bucket name');
    }
  }

  /**
   * 액션 배치를 S3에 업로드
   * @param {Array} actions - 업로드할 액션 배열
   * @param {Object} options - 업로드 옵션
   * @returns {Promise<Object>} 업로드 결과
   */
  async uploadBatch(actions, options = {}) {
    if (!actions || actions.length === 0) {
      return { success: false, message: 'No actions to upload' };
    }

    const timestamp = new Date();
    const batchId = uuidv4();
    
    try {
      // S3 키 생성 (파티션 구조)
      const s3Key = this.generateS3Key(timestamp, actions.length, batchId);
      
      // 업로드할 데이터 구성
      const batchData = {
        batch_id: batchId,
        timestamp: timestamp.toISOString(),
        count: actions.length,
        server_info: {
          hostname: require('os').hostname(),
          version: require('../package.json').version,
          node_version: process.version
        },
        actions: actions.map(action => ({
          ...action,
          batch_id: batchId,
          processed_at: timestamp.toISOString()
        }))
      };

      // JSON 직렬화
      const jsonData = JSON.stringify(batchData, null, 0);
      
      // GZIP 압축 (선택사항 - 용량 절약)
      let bodyData = jsonData;
      let contentEncoding = undefined;
      
      if (options.compress !== false) {
        try {
          bodyData = await gzip(jsonData);
          contentEncoding = 'gzip';
        } catch (compressionError) {
          console.warn('Compression failed, uploading uncompressed:', compressionError.message);
        }
      }

      // S3 업로드 파라미터
      const uploadParams = {
        Bucket: this.bucket,
        Key: s3Key,
        Body: bodyData,
        ContentType: 'application/json',
        Metadata: {
          'batch-id': batchId,
          'action-count': actions.length.toString(),
          'upload-timestamp': timestamp.toISOString(),
          'server-version': require('../package.json').version
        }
      };

      if (contentEncoding) {
        uploadParams.ContentEncoding = contentEncoding;
      }

      // S3 업로드 실행
      const uploadResult = await this.s3.upload(uploadParams).promise();
      
      console.log(`📦 S3 Upload successful: ${actions.length} actions -> ${s3Key}`);
      
      return {
        success: true,
        batch_id: batchId,
        s3_key: s3Key,
        s3_location: uploadResult.Location,
        action_count: actions.length,
        compressed: !!contentEncoding,
        upload_time: new Date() - timestamp
      };

    } catch (error) {
      console.error('❌ S3 Upload failed:', error);
      
      // 에러 타입별 처리
      if (error.code === 'NoSuchBucket') {
        throw new Error(`S3 bucket not found: ${this.bucket}`);
      } else if (error.code === 'AccessDenied') {
        throw new Error('S3 access denied. Please check AWS credentials and permissions');
      } else if (error.code === 'NetworkingError') {
        throw new Error('S3 network error. Please check internet connection');
      }
      
      throw error;
    }
  }

  /**
   * S3 키 생성 (파티션 구조)
   * @param {Date} timestamp - 타임스탬프
   * @param {number} count - 액션 개수
   * @param {string} batchId - 배치 ID
   * @returns {string} S3 키
   */
  generateS3Key(timestamp, count, batchId) {
    const year = timestamp.getFullYear();
    const month = String(timestamp.getMonth() + 1).padStart(2, '0');
    const day = String(timestamp.getDate()).padStart(2, '0');
    const hour = String(timestamp.getHours()).padStart(2, '0');
    const minute = String(timestamp.getMinutes()).padStart(2, '0');
    
    // 파티션 구조: user-actions/year=2025/month=01/day=15/hour=14/
    const partitionPath = `user-actions/year=${year}/month=${month}/day=${day}/hour=${hour}`;
    
    // 파일명: batch-{timestamp}-{count}-{batchId}.json
    const fileName = `batch-${timestamp.getTime()}-${count}-${batchId.slice(0, 8)}.json`;
    
    return `${partitionPath}/${fileName}`;
  }

  /**
   * 테스트용 단일 액션 업로드
   * @param {Object} action - 단일 액션
   * @returns {Promise<Object>} 업로드 결과
   */
  async uploadSingle(action) {
    return await this.uploadBatch([action], { compress: false });
  }

  /**
   * S3 버킷의 파일 목록 조회 (디버깅용)
   * @param {string} prefix - 검색할 접두사
   * @param {number} maxKeys - 최대 결과 수
   * @returns {Promise<Array>} 파일 목록
   */
  async listFiles(prefix = 'user-actions/', maxKeys = 10) {
    try {
      const params = {
        Bucket: this.bucket,
        Prefix: prefix,
        MaxKeys: maxKeys
      };
      
      const result = await this.s3.listObjectsV2(params).promise();
      
      return result.Contents.map(obj => ({
        key: obj.Key,
        size: obj.Size,
        lastModified: obj.LastModified
      }));
      
    } catch (error) {
      console.error('S3 list files failed:', error);
      throw error;
    }
  }

  /**
   * 특정 S3 객체 삭제 (테스트용)
   * @param {string} key - 삭제할 S3 키
   * @returns {Promise<Object>} 삭제 결과
   */
  async deleteObject(key) {
    try {
      const params = {
        Bucket: this.bucket,
        Key: key
      };
      
      await this.s3.deleteObject(params).promise();
      console.log(`🗑️  S3 object deleted: ${key}`);
      
      return { success: true, deleted_key: key };
      
    } catch (error) {
      console.error(`❌ S3 delete failed for ${key}:`, error);
      throw error;
    }
  }

  /**
   * S3 서비스 상태 확인
   * @returns {Promise<Object>} 상태 정보
   */
  async getStatus() {
    try {
      // 버킷 헤드 요청으로 연결 상태 확인
      await this.s3.headBucket({ Bucket: this.bucket }).promise();
      
      // 최근 업로드된 파일 확인
      const recentFiles = await this.listFiles('user-actions/', 1);
      
      return {
        connected: true,
        bucket: this.bucket,
        region: this.s3.config.region,
        recent_files: recentFiles.length,
        last_upload: recentFiles[0]?.lastModified || null
      };
      
    } catch (error) {
      return {
        connected: false,
        bucket: this.bucket,
        region: this.s3.config.region,
        error: error.message
      };
    }
  }
}

module.exports = { S3Service };