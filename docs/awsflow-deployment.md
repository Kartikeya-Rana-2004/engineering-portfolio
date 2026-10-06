# AWSFlow hands-on deployment

## Current status
The source code, offline tests, SDK request-shape verification, and static infrastructure checks are complete. No live AWS resources have been created or cloud queries verified by Codex. Follow this exercise in your own authenticated account to establish actual AWS usage.

The intended exercise uses a small synthetic batch, then optionally a bounded public-data batch. Keep the Free account plan; do not upgrade it for this project. Check the console's credit balance, service availability, and current quotas before deployment; this repository does not verify account billing.

AWS [documents the Free and Paid plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html) separately. The [new-sign-up service list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html) includes this architecture's services, but the new signup experience is rolling out and account-specific access may differ. Service access does not establish that all usage is free or eligible for credits.

## 1. Open CloudShell in US East (N. Virginia)

Use your AWS console's CloudShell under your normal authenticated identity. No credentials need to be pasted into chat. The shell must have permission to deploy the resources in the template and create the scoped Lambda role; do not create long-lived keys for this exercise.

Download the public repository and enter it:

```bash
git clone https://github.com/Kartikeya-Rana-2004/engineering-portfolio.git
cd engineering-portfolio
python3 -m unittest discover -s tests -v
```

## 2. Review and deploy

Review `infra/awsflow/template.json`. It creates one data bucket, one Lambda worker, two SQS queues, an EventBridge rule, scoped worker permissions, two Glue tables, one Athena workgroup, and CloudWatch logs/alarms. The deployment script separately creates a private artifact bucket if absent. It uses no always-on cluster or NAT gateway.

```bash
bash scripts/deploy_awsflow.sh
```

The script explicitly creates resources. It does not change the account plan. Stack outputs give the data bucket, worker name, database, Athena workgroup, and queue URLs. New-account quotas or permissions can still prevent deployment; inspect CloudFormation stack events if it fails.

## 3. Upload and observe the demo

Set the bucket name from the stack output, then upload the three-row synthetic example:

```bash
aws s3 cp examples/requests.jsonl s3://YOUR_DATA_BUCKET/bronze/demo.jsonl --sse AES256 --region us-east-1
```

Watch the EventBridge rule deliver to SQS, then inspect the Lambda log group. S3/EventBridge configuration changes can take time to become effective. Once processed, inspect `silver/`, `audit/`, and `commits/` in the data bucket. No public access is required for these objects.

Uploading again creates a new S3 version/event; it is a new batch, not a duplicate delivery of the old event. The supplied Athena latest view handles overlapping request IDs. The local tests explicitly cover repeated delivery of the same original event.

## 4. Query in Athena

Select the emitted workgroup and database. Run the two `CREATE OR REPLACE VIEW` statements in `infra/awsflow/analytics.sql` separately. Then run the date-bounded metrics query. For the synthetic example, latest records should total 3, of which 2 have closure dates. The final reconciliation query should return no discrepancies.

Capture query results and scanned bytes. The workgroup cancels a query above 100 MiB scanned; this is a per-query limit, not an account-wide spending cap. Small sample sizes and partition filters keep the exercise bounded, but scan volume must be inspected.

## 5. Exercise a failure

```bash
aws s3 cp examples/bad-requests.jsonl s3://YOUR_DATA_BUCKET/bronze/bad-demo.jsonl --sse AES256 --region us-east-1
```

Expect an audit with `blocked_quality_gate`, a quarantine object, no completion marker for that batch, and no new visible committed rows. The quality alarm changes state after its metric evaluation; alarms have no notification destinations configured.

Then examine the worker role: it can read bronze versions and write the selected output prefixes, but cannot administer IAM, delete objects, or query Athena. The operator/query identity needs its own Glue/Athena/S3 permissions and any Lake Formation grants applicable to the account; the worker role is intentionally not reused as an administrator.

## 6. Record evidence and finish the session

Collect a diagram of the deployed services, a successful CloudFormation event, a processed batch log, quarantine evidence, an Athena reconciliation result, and a small query's scanned-byte count. Sanitize account IDs, bucket identifiers, session details, and any private data before publishing screenshots/results. Do not claim a live deployment on a resume until these checks succeed.

Use a short-lived demo session. Delete the CloudFormation stack through the console when finished. The data bucket has `Retain`, so the stack deletion preserves it; empty/delete its current objects and versions, then remove the bucket when you no longer need it. Delete the separately created artifact bucket as well. Retained data may continue consuming credits until cleaned up; lifecycle rules are delayed expiration, not immediate teardown. CloudWatch logs are deleted with the stack. Any future budget alert is a notification, not an enforcement mechanism.

## Resume framing

Before live verification: "Implemented an AWS serverless data-pipeline portfolio project using S3, EventBridge, SQS, Lambda, Glue Data Catalog, Athena, and CloudFormation; verified deterministic replay and failure recovery with automated tests."

After completing the live exercise: add "Deployed and exercised in AWS" and replace sample placeholders with actual measured results. Keep AI-assisted ownership wording appropriate to your own review and contributions. Do not claim Glue ETL/Spark, EMR, Redshift, or a production deployment: those are outside this implementation.
