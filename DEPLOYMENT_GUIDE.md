# RCRAG Service Deployment Guide

## Overview

This guide covers deploying the RCRAG (Reality-Checked RAG) service to Northflank.

## Prerequisites

- Northflank account
- GitHub repository with RCRAG code
- PostgreSQL database (for Historian)
- Neo4j database (optional, for graph features)

## Deployment Steps

### 1. Prepare Repository

```bash
# Ensure all files are committed
git add .
git commit -m "Prepare RCRAG for deployment"
git push origin main
```

### 2. Create Northflank Service

1. Log in to Northflank
2. Create new service
3. Select "Docker" as build type
4. Connect GitHub repository
5. Set build context to `/rcrag-service`
6. Dockerfile path: `Dockerfile`

### 3. Configure Environment Variables

Add these environment variables in Northflank:

**Required:**
- `HISTORIAN_DB_HOST` - PostgreSQL host
- `HISTORIAN_DB_PORT` - PostgreSQL port (default: 5432)
- `HISTORIAN_DB_NAME` - Database name
- `HISTORIAN_DB_USER` - Database user
- `HISTORIAN_DB_PASSWORD` - Database password (use secret)

**Optional:**
- `NEO4J_URI` - Neo4j connection URI
- `NEO4J_USER` - Neo4j username
- `NEO4J_PASSWORD` - Neo4j password (use secret)
- `LOG_LEVEL` - Logging level (default: INFO)
- `PROMETHEUS_ENABLED` - Enable metrics (default: true)
- `CACHE_TTL_SECONDS` - Cache TTL (default: 30)
- `CACHE_MAX_ENTRIES` - Max cache size (default: 1024)

### 4. Configure Resources

**Recommended:**
- CPU: 0.5 - 1.0 vCPU
- Memory: 512MB - 1GB
- Replicas: 2 (for high availability)

### 5. Configure Health Checks

- **Health check path:** `/health`
- **Port:** 8000
- **Initial delay:** 10 seconds
- **Period:** 30 seconds
- **Timeout:** 3 seconds

### 6. Configure Networking

- **Port:** 8000
- **Protocol:** HTTP
- **Public access:** Enable if needed
- **Custom domain:** Optional

### 7. Deploy

1. Click "Deploy"
2. Monitor build logs
3. Wait for service to become healthy
4. Verify deployment

## Verification

### Check Health Endpoint

```bash
curl https://your-service.northflank.app/health
# Expected: {"status":"ok"}
```

### Check Metrics Endpoint

```bash
curl https://your-service.northflank.app/metrics
# Expected: Prometheus metrics in text format
```

### Test Historian API

```bash
# Store a record
curl -X POST https://your-service.northflank.app/api/records \
  -H "Content-Type: application/json" \
  -d '{"content":"test","kind":"test","metadata":{}}'

# Query records
curl https://your-service.northflank.app/api/records?kind=test
```

## Database Setup

### PostgreSQL (Historian)

```sql
-- Create database
CREATE DATABASE historian;

-- Create user
CREATE USER historian_user WITH PASSWORD 'secure_password';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE historian TO historian_user;

-- Enable pgvector extension (for semantic search)
CREATE EXTENSION IF NOT EXISTS vector;
```

### Neo4j (Optional)

```cypher
// Create constraints
CREATE CONSTRAINT record_id IF NOT EXISTS
FOR (r:Record) REQUIRE r.id IS UNIQUE;

// Create indexes
CREATE INDEX record_kind IF NOT EXISTS
FOR (r:Record) ON (r.kind);
```

## Monitoring

### Metrics

Access Prometheus metrics at `/metrics`:

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request duration
- `rcrag_cache_hits_total` - Cache hits
- `rcrag_cache_misses_total` - Cache misses
- `rcrag_rate_limit_hits_total` - Rate limit hits
- `rcrag_circuit_breaker_state` - Circuit breaker state

### Logs

View logs in Northflank dashboard:
- Application logs
- Build logs
- System logs

### Alerts

Configure alerts for:
- Service down
- High error rate
- High response time
- Database connection failures

## Scaling

### Horizontal Scaling

Increase replicas in Northflank:
- 2 replicas: Basic HA
- 3+ replicas: High availability

### Vertical Scaling

Adjust resources:
- CPU: 0.5 - 2.0 vCPU
- Memory: 512MB - 2GB

### Database Scaling

- Enable connection pooling
- Add read replicas
- Optimize queries

## Troubleshooting

### Service Won't Start

1. Check build logs
2. Verify environment variables
3. Check database connectivity
4. Review application logs

### High Response Times

1. Check cache hit rate
2. Review database query performance
3. Check resource utilization
4. Consider scaling

### Database Connection Issues

1. Verify connection string
2. Check firewall rules
3. Verify credentials
4. Check database health

## Rollback

If deployment fails:

1. Go to Northflank dashboard
2. Select previous deployment
3. Click "Rollback"
4. Monitor health checks

## Security

### Secrets Management

- Use Northflank secrets for sensitive data
- Rotate credentials regularly
- Use strong passwords
- Enable encryption at rest

### Network Security

- Use HTTPS only
- Configure firewall rules
- Limit database access
- Use VPC if available

### Application Security

- Keep dependencies updated
- Monitor security advisories
- Use rate limiting
- Implement authentication

## Maintenance

### Updates

```bash
# Update dependencies
pip install --upgrade -r requirements.txt

# Run tests
pytest tests/

# Deploy
git push origin main
```

### Backups

- Database: Daily automated backups
- Configuration: Version control
- Secrets: Secure storage

### Monitoring

- Set up uptime monitoring
- Configure log aggregation
- Enable error tracking
- Monitor resource usage

## Support

For issues:
1. Check logs in Northflank
2. Review this guide
3. Check GitHub issues
4. Contact team

## Next Steps

After deployment:
1. Ingest workflow documentation
2. Build Hub-RCRAG API bridge
3. Test agent access
4. Monitor performance

---

**Status:** Ready for deployment  
**Tests:** 17/17 passing (100%)  
**Documentation:** Complete  
**Next:** Deploy to Northflank
