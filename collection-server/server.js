const express = require('express');
const cors = require('cors');
const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = process.env.PORT || 8080;

// CORS 설정
app.use(cors({
    origin: ['http://localhost:3000', 'http://frontend:3000', 'https://witple.kro.kr'],
    credentials: true
}));

app.use(express.json({ limit: '10mb' }));

// AWS S3 설정
const s3 = new AWS.S3({
    region: process.env.AWS_REGION || 'ap-northeast-2',
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY
});

const BUCKET_NAME = 'user-actions-data';

// 헬스체크 엔드포인트
app.get('/health', (req, res) => {
    res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// 단일 액션 수집 엔드포인트
app.post('/collect', async (req, res) => {
    try {
        const action = req.body;
        
        // 필수 필드 검증
        const requiredFields = ['user_id', 'place_category', 'place_id', 'action_type'];
        for (const field of requiredFields) {
            if (!action[field]) {
                return res.status(400).json({ 
                    error: `Missing required field: ${field}` 
                });
            }
        }
        
        // 타임스탬프와 고유 ID 추가
        const enrichedAction = {
            ...action,
            timestamp: action.timestamp || new Date().toISOString(),
            collection_id: uuidv4(),
            collected_at: new Date().toISOString(),
            server: 'collection-server-docker'
        };
        
        // S3에 저장
        const key = `user-actions/${new Date().toISOString().split('T')[0]}/${enrichedAction.collection_id}.json`;
        
        await s3.putObject({
            Bucket: BUCKET_NAME,
            Key: key,
            Body: JSON.stringify(enrichedAction),
            ContentType: 'application/json'
        }).promise();
        
        console.log(`✅ Action collected: ${action.action_type} for ${action.place_category} by ${action.user_id.substring(0, 8)}...`);
        
        res.json({ 
            success: true, 
            collection_id: enrichedAction.collection_id,
            s3_key: key
        });
        
    } catch (error) {
        console.error('❌ Collection error:', error);
        res.status(500).json({ error: 'Failed to collect action' });
    }
});

// 배치 액션 수집 엔드포인트
app.post('/collect-batch', async (req, res) => {
    try {
        const { actions } = req.body;
        
        if (!actions || !Array.isArray(actions)) {
            return res.status(400).json({ error: 'actions array is required' });
        }
        
        const results = [];
        
        for (const action of actions) {
            try {
                const enrichedAction = {
                    ...action,
                    timestamp: action.timestamp || new Date().toISOString(),
                    collection_id: uuidv4(),
                    collected_at: new Date().toISOString(),
                    server: 'collection-server-docker'
                };
                
                const key = `user-actions/${new Date().toISOString().split('T')[0]}/${enrichedAction.collection_id}.json`;
                
                await s3.putObject({
                    Bucket: BUCKET_NAME,
                    Key: key,
                    Body: JSON.stringify(enrichedAction),
                    ContentType: 'application/json'
                }).promise();
                
                results.push({ success: true, collection_id: enrichedAction.collection_id });
                
            } catch (error) {
                console.error(`❌ Error processing action:`, error);
                results.push({ success: false, error: error.message });
            }
        }
        
        console.log(`📦 Batch processed: ${results.filter(r => r.success).length}/${actions.length} actions`);
        
        res.json({ 
            success: true, 
            processed: results.length,
            successful: results.filter(r => r.success).length,
            results 
        });
        
    } catch (error) {
        console.error('❌ Batch collection error:', error);
        res.status(500).json({ error: 'Failed to collect batch actions' });
    }
});

app.listen(PORT, () => {
    console.log(`🚀 Collection Server running on port ${PORT}`);
    console.log(`📡 Ready to collect user actions to S3 bucket: ${BUCKET_NAME}`);
});