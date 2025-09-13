const { S3Service } = require('./s3Service');

class BufferService {
  constructor() {
    this.buffer = [];
    this.maxBufferSize = parseInt(process.env.MAX_BUFFER_SIZE) || 100;
    this.maxBufferAge = parseInt(process.env.MAX_BUFFER_AGE) || 300000; // 5분
    this.s3Service = new S3Service();
    
    // 통계 정보
    this.stats = {
      totalReceived: 0,
      totalUploaded: 0,
      totalFailed: 0,
      immediateUploads: 0,
      batchUploads: 0,
      bufferFlushes: 0,
      lastFlushTime: null,
      startTime: new Date()
    };
    
    console.log(`🔧 BufferService initialized:`);
    console.log(`   - Max buffer size: ${this.maxBufferSize}`);
    console.log(`   - Max buffer age: ${this.maxBufferAge / 1000}s`);
  }

  /**
   * 버퍼에 액션 추가 (일반 액션용)
   * @param {Object} action - 추가할 액션
   * @returns {Promise<Object>} 처리 결과
   */
  async addToBuffer(action) {
    try {
      // 액션에 메타데이터 추가
      const enrichedAction = {
        ...action,
        buffer_received_at: new Date().toISOString(),
        buffer_id: this.generateBufferId()
      };

      this.buffer.push(enrichedAction);
      this.stats.totalReceived++;
      
      console.log(`📥 Action buffered: ${action.action_type} (buffer size: ${this.buffer.length}/${this.maxBufferSize})`);
      
      // 버퍼가 가득 찬 경우 자동 플러시
      if (this.buffer.length >= this.maxBufferSize) {
        console.log(`🚀 Buffer full, triggering flush...`);
        const flushResult = await this.flushToS3();
        return {
          buffered: true,
          auto_flushed: true,
          flush_result: flushResult
        };
      }
      
      return {
        buffered: true,
        buffer_size: this.buffer.length,
        auto_flushed: false
      };
      
    } catch (error) {
      console.error('❌ Buffer add failed:', error);
      throw error;
    }
  }

  /**
   * 중요 액션 즉시 S3 업로드 (좋아요, 북마크용)
   * @param {Object} action - 즉시 업로드할 액션
   * @returns {Promise<Object>} 업로드 결과
   */
  async sendImmediately(action) {
    try {
      const enrichedAction = {
        ...action,
        immediate_upload: true,
        uploaded_at: new Date().toISOString()
      };

      console.log(`⚡ Immediate upload: ${action.action_type} for user ${action.user_id}`);
      
      const uploadResult = await this.s3Service.uploadSingle(enrichedAction);
      
      if (uploadResult.success) {
        this.stats.totalUploaded++;
        this.stats.immediateUploads++;
        console.log(`✅ Immediate upload successful: ${uploadResult.batch_id}`);
      } else {
        this.stats.totalFailed++;
        console.error('❌ Immediate upload failed');
      }
      
      return {
        immediate: true,
        upload_result: uploadResult
      };
      
    } catch (error) {
      this.stats.totalFailed++;
      console.error(`❌ Immediate upload failed for ${action.action_type}:`, error);
      
      // 실패한 중요 액션은 버퍼에 추가하여 재시도
      console.log('🔄 Adding failed immediate action to buffer for retry...');
      return await this.addToBuffer({
        ...action,
        immediate_failed: true,
        immediate_error: error.message
      });
    }
  }

  /**
   * 버퍼의 모든 액션을 S3로 플러시
   * @returns {Promise<Object>} 플러시 결과
   */
  async flushToS3() {
    if (this.buffer.length === 0) {
      return {
        success: true,
        message: 'Buffer is empty',
        count: 0
      };
    }

    // 현재 버퍼 내용을 복사하고 버퍼 클리어
    const actionsToSend = [...this.buffer];
    this.buffer = [];
    
    console.log(`🚀 Flushing buffer: ${actionsToSend.length} actions`);
    
    try {
      const uploadResult = await this.s3Service.uploadBatch(actionsToSend);
      
      if (uploadResult.success) {
        this.stats.totalUploaded += actionsToSend.length;
        this.stats.batchUploads++;
        this.stats.bufferFlushes++;
        this.stats.lastFlushTime = new Date();
        
        console.log(`✅ Buffer flush successful: ${actionsToSend.length} actions uploaded`);
        console.log(`📊 Batch ID: ${uploadResult.batch_id}`);
        console.log(`📍 S3 Location: ${uploadResult.s3_key}`);
        
        return {
          success: true,
          count: actionsToSend.length,
          batch_id: uploadResult.batch_id,
          s3_key: uploadResult.s3_key,
          upload_time: uploadResult.upload_time
        };
      } else {
        throw new Error(uploadResult.message || 'Upload failed');
      }
      
    } catch (error) {
      this.stats.totalFailed += actionsToSend.length;
      console.error('❌ Buffer flush failed:', error);
      
      // 실패한 액션들을 버퍼에 다시 추가 (최대 50개까지만)
      const actionsToRestore = actionsToSend
        .slice(0, 50)
        .map(action => ({
          ...action,
          retry_count: (action.retry_count || 0) + 1,
          last_retry_error: error.message,
          last_retry_at: new Date().toISOString()
        }))
        .filter(action => (action.retry_count || 0) < 3); // 최대 3회 재시도
      
      if (actionsToRestore.length > 0) {
        this.buffer.unshift(...actionsToRestore);
        console.log(`🔄 ${actionsToRestore.length} actions restored to buffer for retry`);
      }
      
      const discardedCount = actionsToSend.length - actionsToRestore.length;
      if (discardedCount > 0) {
        console.warn(`⚠️  ${discardedCount} actions discarded (max retries exceeded)`);
      }
      
      return {
        success: false,
        error: error.message,
        attempted_count: actionsToSend.length,
        restored_count: actionsToRestore.length,
        discarded_count: discardedCount
      };
    }
  }

  /**
   * 오래된 액션들을 강제로 플러시 (age-based)
   * @returns {Promise<Object>} 플러시 결과
   */
  async flushOldActions() {
    if (this.buffer.length === 0) {
      return { success: true, message: 'Buffer is empty', count: 0 };
    }

    const now = new Date();
    const oldActions = [];
    const newActions = [];
    
    // 버퍼의 액션들을 나이별로 분리
    for (const action of this.buffer) {
      const actionAge = now - new Date(action.buffer_received_at);
      if (actionAge > this.maxBufferAge) {
        oldActions.push(action);
      } else {
        newActions.push(action);
      }
    }
    
    if (oldActions.length === 0) {
      return { success: true, message: 'No old actions to flush', count: 0 };
    }
    
    // 새 액션들만 버퍼에 남기고, 오래된 액션들은 업로드
    this.buffer = newActions;
    
    console.log(`⏰ Flushing ${oldActions.length} old actions (age > ${this.maxBufferAge/1000}s)`);
    
    try {
      const uploadResult = await this.s3Service.uploadBatch(oldActions);
      
      if (uploadResult.success) {
        this.stats.totalUploaded += oldActions.length;
        console.log(`✅ Old actions flush successful: ${oldActions.length} actions`);
        
        return {
          success: true,
          count: oldActions.length,
          reason: 'age-based-flush',
          batch_id: uploadResult.batch_id
        };
      }
      
    } catch (error) {
      // 실패한 경우 오래된 액션들을 버퍼 앞쪽에 다시 추가
      this.buffer.unshift(...oldActions);
      console.error('❌ Old actions flush failed:', error);
      
      return {
        success: false,
        error: error.message,
        attempted_count: oldActions.length
      };
    }
  }

  /**
   * 버퍼 상태 조회
   * @returns {Object} 버퍼 상태 정보
   */
  getBufferStatus() {
    const now = new Date();
    const oldestAction = this.buffer.length > 0 
      ? this.buffer.reduce((oldest, action) => {
          const actionTime = new Date(action.buffer_received_at);
          return actionTime < new Date(oldest.buffer_received_at) ? action : oldest;
        })
      : null;
    
    return {
      buffer_size: this.buffer.length,
      max_buffer_size: this.maxBufferSize,
      buffer_usage_percent: Math.round((this.buffer.length / this.maxBufferSize) * 100),
      oldest_action_age: oldestAction 
        ? Math.round((now - new Date(oldestAction.buffer_received_at)) / 1000)
        : 0,
      max_age_seconds: this.maxBufferAge / 1000,
      needs_flush: this.buffer.length >= this.maxBufferSize,
      needs_age_flush: oldestAction 
        ? (now - new Date(oldestAction.buffer_received_at)) > this.maxBufferAge
        : false
    };
  }

  /**
   * 서비스 통계 조회
   * @returns {Object} 통계 정보
   */
  getStats() {
    const uptime = new Date() - this.stats.startTime;
    const uptimeHours = Math.round(uptime / (1000 * 60 * 60) * 100) / 100;
    
    return {
      ...this.stats,
      uptime_hours: uptimeHours,
      success_rate: this.stats.totalReceived > 0 
        ? Math.round((this.stats.totalUploaded / this.stats.totalReceived) * 100)
        : 100,
      actions_per_hour: uptimeHours > 0 
        ? Math.round(this.stats.totalReceived / uptimeHours)
        : 0,
      last_flush_ago: this.stats.lastFlushTime 
        ? Math.round((new Date() - this.stats.lastFlushTime) / 1000)
        : null
    };
  }

  /**
   * 버퍼 ID 생성 (디버깅용)
   */
  generateBufferId() {
    return `buf_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
  }

  /**
   * 버퍼 강제 클리어 (긴급상황용)
   */
  clearBuffer() {
    const clearedCount = this.buffer.length;
    this.buffer = [];
    console.log(`🧹 Buffer forcefully cleared: ${clearedCount} actions discarded`);
    return { cleared: clearedCount };
  }
}

// 싱글톤 인스턴스 생성
const bufferService = new BufferService();

module.exports = { bufferService, BufferService };