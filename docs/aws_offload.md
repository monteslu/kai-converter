# AWS GPU Offload Plan for KAI-Pack Processing

## Overview
Move KAI-Pack processing to AWS GPU instances for faster, higher-quality transcription and stem separation while maintaining cost target of ~10 cents per song.

## Architecture

### Option A: ECS Fargate + Spot GPU (Recommended)
- **Container**: Docker image with kai-pack + GPU dependencies
- **Compute**: ECS Fargate with GPU (g5.xlarge spot instances)
- **Storage**: EFS for model caching, S3 for input/output files
- **Queue**: SQS for job management
- **API**: Lambda for job submission/status

### Option B: Batch + EC2 Spot
- **Compute**: AWS Batch with EC2 GPU spot instances
- **Queue**: Built-in Batch job queue
- **Storage**: S3 for all file operations

## Enhanced Processing Configuration

### Whisper Settings
```bash
--whisper-model large-v3
--language en
--word_timestamps true
--device cuda
```

### Demucs Premium Settings
```bash
--model mdx_extra_q          # Highest quality model
--overlap 0.5                # Better quality separation
--shifts 5                   # Multiple predictions averaged
--sr 48000                   # Higher sample rate
--device cuda
--stem-bitrate 320k          # Higher quality MP3 encoding
```

### Audio Profile Upgrades
- **KAI-6**: Enable 6-stem separation (vocals, drums, bass, guitar, piano, other)
- **Higher bitrates**: 320k for all stems vs current 160k
- **48kHz processing**: vs current 44.1kHz

## Infrastructure Components

### 1. Container Image
```dockerfile
FROM nvidia/cuda:11.8-devel-ubuntu22.04
# Install Python, PyTorch with CUDA, Whisper, Demucs
# Copy kai-pack source code
# Pre-download models to reduce cold start
```

### 2. ECS Task Definition
```json
{
  "requiresAttributes": [{"name": "com.amazonaws.ecs.capability.docker-gpu"}],
  "memory": 16384,
  "cpu": 4096,
  "resourceRequirements": [
    {"type": "GPU", "value": "1"}
  ]
}
```

### 3. Job Submission API
```python
# Lambda function
def submit_job(mp3_url, options):
    # Upload MP3 to S3
    # Submit ECS task with job parameters
    # Return job ID for status checking
```

### 4. Processing Workflow
1. **Job Submission**: API receives MP3 + options
2. **File Upload**: Store MP3 in S3
3. **Task Launch**: ECS starts GPU container
4. **Processing**: Run kai-pack with premium settings
5. **Output**: Upload .kai file to S3
6. **Notification**: Update job status/webhook

## Cost Analysis

### Compute Costs (per song, ~1-2 minutes processing)
- **g4dn.xlarge spot**: ~$0.003 per song
- **g5.xlarge spot**: ~$0.006 per song  
- **g5.2xlarge spot**: ~$0.012 per song (for batch processing)

### Storage Costs
- **S3 storage**: $0.001 per song (temporary)
- **Data transfer**: $0.002 per song
- **EFS model cache**: $0.001 per song

### **Total Cost**: $0.01-0.02 per song (well under 10¢ target)

## Performance Expectations

### Current (CPU)
- **Time**: 3-4 minutes per song
- **Quality**: Good (tiny Whisper, htdemucs_ft)
- **Cost**: Free (local processing)

### AWS GPU (Projected)
- **Time**: 30-90 seconds per song
- **Quality**: Excellent (large-v3 Whisper, mdx_extra_q)
- **Cost**: 1-2 cents per song
- **Stems**: 6-stem separation available
- **Bitrate**: 320k vs 160k

## Implementation Phases

### Phase 1: Basic GPU Migration
- Containerize existing kai-pack
- Deploy on g5.xlarge spot
- Use large-v3 Whisper model
- Keep current 4-stem Demucs

### Phase 2: Quality Enhancements  
- Upgrade to mdx_extra_q Demucs
- Enable 6-stem separation
- Increase overlap/shifts for quality
- 320k bitrate encoding

### Phase 3: Production Features
- Batch processing for multiple songs
- WebSocket status updates
- Cost optimization with mixed instance types
- Auto-scaling based on queue depth

## API Design

### Job Submission
```http
POST /jobs
{
  "mp3_url": "https://...",
  "options": {
    "whisper_model": "large-v3",
    "demucs_model": "mdx_extra_q", 
    "audio_profile": "KAI-6",
    "stem_bitrate": "320k"
  }
}
```

### Job Status
```http
GET /jobs/{job_id}
{
  "status": "processing|completed|failed",
  "progress": 65,
  "kai_url": "https://...",
  "processing_time": 47,
  "cost": 0.018
}
```

## Monitoring & Optimization

### Metrics to Track
- Processing time per song/model combination
- Cost per song by instance type
- Queue wait times
- Success/failure rates

### Cost Optimizations
- **Mixed instances**: Use smaller instances for short songs
- **Batch processing**: Process multiple songs per container
- **Model caching**: Keep hot models in memory
- **Spot instance strategies**: Fallback to on-demand if needed

## Next Steps
1. Create Dockerfile with CUDA + kai-pack
2. Set up ECS cluster with GPU support
3. Build job submission/status API
4. Test processing time/quality with different models
5. Implement cost monitoring and optimization