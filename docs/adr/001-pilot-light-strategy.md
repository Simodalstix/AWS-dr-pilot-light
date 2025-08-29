# ADR-001: Pilot Light DR Strategy

## Status
Accepted

## Context
Need to implement disaster recovery for e-commerce platform with strict RTO/RPO requirements while maintaining cost efficiency.

## Decision
Implement Pilot Light strategy with:
- RDS read replica in DR region (continuous sync)
- Auto Scaling Groups scaled to 0 (instant activation)
- Step Functions orchestration for complex failover workflows
- Route 53 health checks for automated DNS failover

## Consequences

### Positive
- 80% cost reduction vs warm standby
- 3-5 minute automated RTO
- <1 minute database RPO
- Automated validation and rollback

### Negative
- Slightly longer RTO than warm standby
- Requires complex orchestration logic
- Cross-region data transfer costs

## Alternatives Considered
- **Backup/Restore**: Too slow (hours RTO)
- **Warm Standby**: 5x more expensive
- **Multi-Site Active**: Unnecessary complexity for this use case