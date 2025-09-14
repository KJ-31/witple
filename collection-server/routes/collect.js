const express = require('express');
const { bufferService } = require('../services/bufferService');

const router = express.Router();

/**
 * 데이터 수집 엔드포인트 - actionTracker.ts와 완벽 호환
 * POST /collect
 */
router.post('/', async (req, res) => {
  try {
    // 디버깅: 받은 데이터 로깅
    console.log('📨 Received request body:', JSON.stringify(req.body, null, 2));
    
    // 동적으로 데이터 형식 감지 및 처리
    let actionsToProcess = [];
    
    if (req.body.actions && Array.isArray(req.body.actions)) {
      // actionTracker.ts 형식: {actions: [액션들]}
      actionsToProcess = req.body.actions;
      console.log('📋 Processing actions array:', actionsToProcess.length, 'actions');
    } else if (req.body.user_id || req.body.place_id || req.body.action_type) {
      // 단일 액션 객체 형식: {user_id, place_id, action_type, ...}
      actionsToProcess = [req.body];
      console.log('📄 Processing single action object');
    } else {
      console.log('❌ Invalid request format - body keys:', Object.keys(req.body));
      throw new Error('Invalid request format. Expected either {actions: [...]} or single action object');
    }
    
    if (actionsToProcess.length === 0) {
      throw new Error('No actions to process');
    }
    
    const results = [];
    
    // 각 액션 처리
    for (const actionData of actionsToProcess) {
      // 요청 데이터 검증
      const action = validateActionData(actionData);
      
      // 액션에 서버 메타데이터 추가
      const enrichedAction = {
        ...action,
        server_timestamp: new Date().toISOString(),
        server_received_at: Date.now(),
        client_ip: getClientIP(req),
        user_agent: req.get('User-Agent') || 'unknown',
        request_id: generateRequestId()
      };

      // 액션 타입별 처리 분기 (환경변수 또는 설정으로 제어 가능)
      const isImmediateAction = isActionImmediate(action.action_type);
      let processingResult;
      
      if (isImmediateAction) {
        // 중요 액션은 즉시 S3 업로드
        console.log(`⚡ Processing immediate action: ${action.action_type} - user: ${action.user_id}`);
        processingResult = await bufferService.sendImmediately(enrichedAction);
      } else {
        // 일반 액션은 버퍼에 추가 (5분마다 또는 100개씩 배치 전송)
        console.log(`📥 Processing batch action: ${action.action_type} - user: ${action.user_id}`);
        processingResult = await bufferService.addToBuffer(enrichedAction);
      }
      
      // 결과 저장
      results.push({
        action_id: enrichedAction.request_id,
        processed: true,
        processing_result: processingResult
      });
      
      // 액션 로깅 (상세 정보)
      logActionDetails(enrichedAction, processingResult);
    }
    
    // 성공 응답 (actionTracker.ts가 기대하는 형식)
    res.json({
      success: true,
      received: new Date().toISOString(),
      actions_processed: results.length,
      results: results
    });
    
  } catch (error) {
    console.error('❌ Collection endpoint error:', error);
    
    // 에러 응답 (actionTracker.ts가 재시도할 수 있도록)
    res.status(500).json({
      success: false,
      error: 'Collection failed',
      message: error.message,
      timestamp: new Date().toISOString(),
      retry_recommended: true
    });
  }
});

/**
 * 버퍼 상태 조회 (모니터링용)
 * GET /collect/status
 */
router.get('/status', (req, res) => {
  try {
    const bufferStatus = bufferService.getBufferStatus();
    const stats = bufferService.getStats();
    
    res.json({
      status: 'operational',
      timestamp: new Date().toISOString(),
      buffer: bufferStatus,
      statistics: stats,
      health: {
        memory_usage: process.memoryUsage(),
        uptime: process.uptime(),
        cpu_usage: process.cpuUsage()
      }
    });
    
  } catch (error) {
    console.error('Status check failed:', error);
    res.status(500).json({
      status: 'error',
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

/**
 * 수동 버퍼 플러시 (관리용)
 * POST /collect/flush
 */
router.post('/flush', async (req, res) => {
  try {
    console.log('🔧 Manual buffer flush requested');
    const flushResult = await bufferService.flushToS3();
    
    res.json({
      success: true,
      message: 'Buffer flush completed',
      result: flushResult,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    console.error('Manual flush failed:', error);
    res.status(500).json({
      success: false,
      error: 'Manual flush failed',
      message: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

/**
 * 버퍼 클리어 (긴급용)
 * POST /collect/clear
 */
router.post('/clear', (req, res) => {
  try {
    console.log('🚨 Manual buffer clear requested');
    const clearResult = bufferService.clearBuffer();
    
    res.json({
      success: true,
      message: 'Buffer cleared',
      cleared_count: clearResult.cleared,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    console.error('Buffer clear failed:', error);
    res.status(500).json({
      success: false,
      error: 'Buffer clear failed',
      message: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// ============= 유틸리티 함수들 =============

/**
 * actionTracker.ts 데이터 형식 검증
 * @param {Object} data - 요청 데이터
 * @returns {Object} 검증된 액션 데이터
 */
function validateActionData(data) {
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid request data: must be an object');
  }

  // actionTracker.ts에서 보내는 필수 필드들
  const requiredFields = ['user_id', 'place_category', 'place_id', 'action_type'];
  const missingFields = requiredFields.filter(field => !data[field]);
  
  if (missingFields.length > 0) {
    throw new Error(`Missing required fields: ${missingFields.join(', ')}`);
  }

  // 액션 타입 검증
  const validActionTypes = ['click', 'like', 'bookmark'];
  if (!validActionTypes.includes(data.action_type)) {
    console.warn(`⚠️  Unknown action type: ${data.action_type}`);
  }

  // 데이터 정제 및 타입 변환
  return {
    user_id: String(data.user_id).trim(),
    place_category: String(data.place_category).trim(),
    place_id: String(data.place_id).trim(),
    action_type: String(data.action_type).toLowerCase().trim(),
    action_value: data.action_value ? parseInt(data.action_value) : null,
    action_detail: data.action_detail || null,
    
    // actionTracker.ts의 추가 필드들
    session_id: data.session_id || null,
    timestamp: data.timestamp || new Date().toISOString(),
    
    // 클라이언트 메타데이터 (있으면 보존)
    client_timestamp: data.timestamp || null,
    client_url: data.client_url || null,
    component: data.component || null
  };
}

/**
 * 클라이언트 IP 추출
 * @param {Object} req - Express request 객체
 * @returns {string} 클라이언트 IP
 */
function getClientIP(req) {
  return req.ip || 
         req.connection.remoteAddress || 
         req.socket.remoteAddress ||
         (req.connection.socket ? req.connection.socket.remoteAddress : null) ||
         'unknown';
}

/**
 * 요청 ID 생성
 * @returns {string} 고유 요청 ID
 */
function generateRequestId() {
  return `req_${Date.now()}_${Math.random().toString(36).substr(2, 8)}`;
}

/**
 * 액션 처리 상세 로깅
 * @param {Object} action - 처리된 액션
 * @param {Object} result - 처리 결과
 */
/**
 * 액션이 즉시 처리되어야 하는지 동적으로 판단
 */
function isActionImmediate(actionType) {
  // 환경변수로 즉시 처리할 액션 타입들 설정 가능
  const immediateActionsEnv = process.env.IMMEDIATE_ACTIONS || 'like,bookmark';
  const immediateActions = immediateActionsEnv.split(',').map(a => a.trim().toLowerCase());
  
  return immediateActions.includes(actionType.toLowerCase());
}

function logActionDetails(action, result) {
  const isImmediate = isActionImmediate(action.action_type);
  const logLevel = isImmediate ? 'IMPORTANT' : 'INFO';
  const processingType = result.immediate ? 'IMMEDIATE' : 'BUFFERED';
  
  console.log(`[${logLevel}] ${processingType} | ${action.action_type.toUpperCase()} | User: ${action.user_id} | Place: ${action.place_category}:${action.place_id} | ID: ${action.request_id}`);
  
  // 중요한 액션들의 상세 로깅
  if (isImmediate) {
    console.log(`   ├─ Value: ${action.action_value}, Session: ${action.session_id}`);
    console.log(`   ├─ Client IP: ${action.client_ip}`);
    console.log(`   └─ Processing time: ${Date.now() - action.server_received_at}ms`);
  }
}

module.exports = router;