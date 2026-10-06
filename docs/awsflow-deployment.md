# AWSFlow: preparation without cloud charges

The active project constraint is **$0 out-of-pocket**. Live deployment is disabled. No AWS resources were created during project work.

## Run and demonstrate locally

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 -m awsflow.demo
python3 infra/build_awsflow.py
bash scripts/deploy_awsflow.sh
```

The last command is retained for compatibility but now only builds local template/ZIP files. It does not authenticate to AWS, upload objects, or create a stack. Deployment arguments are rejected.

To validate SDK request shapes and infrastructure locally:

```bash
python3 -m pip install -r requirements-aws-dev.txt
python3 scripts/verify_aws_sdk.py
cfn-lint infra/awsflow/template.json
```

Review the generated CloudFormation template, scoped IAM policies, event filter, queue retries, commit-last worker, and Athena SQL. Demonstrate duplicate-event stability and recovery after an injected output failure. These checks establish implementation behavior, not live AWS usage.

## Any later live exercise

A live exercise requires a verified account plan and a route that preserves the $0 constraint. Having credits on a Paid plan is insufficient. Do not upgrade the account or activate paid-only services to follow this project. No deployment automation is enabled here.

The template remains usable infrastructure code; manually deploying it in the console can create resources and consume credits or incur charges depending on the account. It is outside the current local-only workflow.

See the [cost policy](cost-policy.md), [AWS Free account plan documentation](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html), and [account plan details](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html). The account's billing state has not been inspected.

## Resume framing

Current evidence supports: "Implemented an AWS serverless data-pipeline portfolio project using S3, EventBridge, SQS, Lambda, Glue Data Catalog, Athena, and CloudFormation; verified deterministic replay and failure recovery with automated tests."

Only add "deployed and exercised in AWS" after actual cloud deployment and successful verification. Glue here is catalog metadata; Glue ETL/Spark, EMR, and Redshift are outside this implementation.
