# ADR-0003: Run the AWS deployment in demo windows

- **Status:** Accepted
- **Date:** 2026-10-15
- **Phase:** 8 (decided during planning)

## Context

The project needs a production-shaped AWS deployment (containers behind a load balancer, managed Postgres, queues, secrets, monitoring) that can be demonstrated, without paying for it while nobody is using it.

## Options considered

| Option | Rough cost | Pros | Cons |
|---|---|---|---|
| Always-on production shape (ECS services, load balancer, RDS) | About $80–100 a month | Always reachable | Pays for idle time |
| Lean mode: the same containers on one EC2 instance | About $20–30 a month | Cheap and always reachable | Not the production shape |
| **Demo windows: bring the full stack up for a demo, tear it down after** | A few dollars per demo (to be measured) | Production shape at minimal cost | Not reachable between demos; bring-up takes several minutes |

## Decision

Use demo windows. Terraform brings the production-shaped stack up for a demo or a recording and tears it down afterwards.

## Consequences

- Terraform is split into a small **persistent** layer and an ephemeral **demo** layer. The persistent layer holds the state bucket, ECR repositories, the S3 data bucket, the budget alarm, the GitHub OIDC role and the HTTPS front door. The demo layer holds the VPC, ECS services, load balancer, RDS, SQS, DynamoDB, Secrets Manager entries and CloudWatch.
- HTTPS needs a name we control. ACM cannot issue a certificate for the load balancer's own `*.elb.amazonaws.com` address, and that address changes on every bring-up. The choice between a custom domain with an ACM certificate and CloudFront's default certificate in front of the load balancer is made in Phase 8. Either way, it sits in the persistent layer so the public URL stays stable across demos.
- RDS is restored from a snapshot on bring-up and snapshotted on teardown, so data survives between demos.
- `demo-up` and `demo-down` tasks wrap Terraform. A scheduled CI job tears the demo layer down if it is left running past a time limit.
- Region: `ap-south-1` (Mumbai), the closest to the developer.
- Between demos, the project is shown through the repository, the project page on GitHub Pages and a recorded demo video. Docker Compose remains the everyday environment.
- Qdrant Cloud's policy on idle free clusters is checked in Phase 8. Collections are snapshotted to S3 so they can be restored.
- Exact costs are measured during the first demo window and recorded in the Phase 8 eval report.

## References

- AWS Pricing Calculator: https://calculator.aws/
- Terraform `aws_db_instance` (`snapshot_identifier`, `final_snapshot_identifier`): https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance
- AWS Certificate Manager, *Requesting a public certificate* (domain validation): https://docs.aws.amazon.com/acm/latest/userguide/gs-acm-request-public.html
