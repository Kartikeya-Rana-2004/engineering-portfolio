"""Build a reviewable CloudFormation template and a deterministic Lambda ZIP."""
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "infra/awsflow"


def ref(name):
    return {"Ref": name}


def sub(value):
    return {"Fn::Sub": value}


def attr(name, value="Arn"):
    return {"Fn::GetAtt": [name, value]}


def resource(kind, properties, **extra):
    return {"Type": kind, "Properties": properties, **extra}


def template():
    r = {}
    r["DataBucket"] = resource("AWS::S3::Bucket", {
        "VersioningConfiguration": {"Status": "Enabled"},
        "BucketEncryption": {"ServerSideEncryptionConfiguration": [{"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]},
        "PublicAccessBlockConfiguration": {k: True for k in ("BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets")},
        "NotificationConfiguration": {"EventBridgeConfiguration": {"EventBridgeEnabled": True}},
        "LifecycleConfiguration": {"Rules": [{"Id": "DemoRetention", "Status": "Enabled", "ExpirationInDays": 30, "NoncurrentVersionExpiration": {"NoncurrentDays": 7}, "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}}]},
    }, DeletionPolicy="Retain", UpdateReplacePolicy="Retain")
    r["BucketPolicy"] = resource("AWS::S3::BucketPolicy", {"Bucket": ref("DataBucket"), "PolicyDocument": {
        "Version": "2012-10-17", "Statement": [{"Effect": "Deny", "Principal": "*", "Action": "s3:*", "Resource": [attr("DataBucket"), sub("${DataBucket.Arn}/*")], "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}})
    r["DeadLetterQueue"] = resource("AWS::SQS::Queue", {"SqsManagedSseEnabled": True, "MessageRetentionPeriod": 1209600})
    r["WorkQueue"] = resource("AWS::SQS::Queue", {"SqsManagedSseEnabled": True, "VisibilityTimeout": 720, "MessageRetentionPeriod": 345600, "RedrivePolicy": {"deadLetterTargetArn": attr("DeadLetterQueue"), "maxReceiveCount": 5}})
    r["WorkerRole"] = resource("AWS::IAM::Role", {
        "AssumeRolePolicyDocument": {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]},
        "Policies": [{"PolicyName": "DataAndQueue", "PolicyDocument": {"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Action": ["s3:GetObject", "s3:GetObjectVersion"], "Resource": sub("${DataBucket.Arn}/bronze/*")},
            {"Effect": "Allow", "Action": "s3:PutObject", "Resource": [sub("${DataBucket.Arn}/" + prefix + "/*") for prefix in ("silver", "quarantine", "audit", "commits")]},
            {"Effect": "Allow", "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], "Resource": attr("WorkQueue")},
        ]}}],
    })
    r["Worker"] = resource("AWS::Lambda::Function", {
        "Runtime": "python3.12", "Handler": "awsflow.worker.lambda_handler", "Role": attr("WorkerRole"),
        "Code": {"S3Bucket": ref("ArtifactBucket"), "S3Key": ref("ArtifactKey")},
        "Timeout": 120, "MemorySize": 512,
        "Environment": {"Variables": {"DATA_BUCKET": ref("DataBucket"), "MAX_BYTES": "8388608"}},
    })
    r["WorkerLogGroup"] = resource("AWS::Logs::LogGroup", {"LogGroupName": sub("/aws/lambda/${Worker}"), "RetentionInDays": 7})
    r["WorkerLogsPolicy"] = resource("AWS::IAM::Policy", {"PolicyName": "WorkerLogs", "Roles": [ref("WorkerRole")], "PolicyDocument": {
        "Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"], "Resource": attr("WorkerLogGroup")}]}})
    r["QueueMapping"] = resource("AWS::Lambda::EventSourceMapping", {
        "EventSourceArn": attr("WorkQueue"), "FunctionName": ref("Worker"), "BatchSize": 5,
        "FunctionResponseTypes": ["ReportBatchItemFailures"], "ScalingConfig": {"MaximumConcurrency": 2}, "Enabled": True,
    }, DependsOn=["WorkerLogsPolicy"])
    r["BronzeRule"] = resource("AWS::Events::Rule", {
        "EventPattern": {"source": ["aws.s3"], "detail-type": ["Object Created"], "detail": {"bucket": {"name": [ref("DataBucket")]}, "object": {"key": [{"prefix": "bronze/"}]}}},
        "Targets": [{"Id": "Queue", "Arn": attr("WorkQueue"), "RetryPolicy": {"MaximumRetryAttempts": 10, "MaximumEventAgeInSeconds": 3600}, "DeadLetterConfig": {"Arn": attr("DeadLetterQueue")}}],
    })
    r["QueuePolicy"] = resource("AWS::SQS::QueuePolicy", {"Queues": [ref("WorkQueue"), ref("DeadLetterQueue")], "PolicyDocument": {
        "Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "events.amazonaws.com"}, "Action": "sqs:SendMessage", "Resource": [attr("WorkQueue"), attr("DeadLetterQueue")], "Condition": {"ArnEquals": {"aws:SourceArn": attr("BronzeRule")}}}]}})
    r["Database"] = resource("AWS::Glue::Database", {"CatalogId": ref("AWS::AccountId"), "DatabaseInput": {"Name": ref("DatabaseName")}})
    columns = [("unique_key", "string"), ("created_date", "string"), ("closed_date", "string"), ("agency", "string"), ("complaint_type", "string"), ("borough", "string"), ("status", "string"), ("resolution_hours", "double"), ("batch_id", "string"), ("ingested_at", "string")]
    storage = lambda location, fields: {"Location": location, "InputFormat": "org.apache.hadoop.mapred.TextInputFormat", "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat", "SerdeInfo": {"SerializationLibrary": "org.apache.hive.hcatalog.data.JsonSerDe"}, "Columns": [{"Name": name, "Type": kind} for name, kind in fields]}
    r["SilverTable"] = resource("AWS::Glue::Table", {"CatalogId": ref("AWS::AccountId"), "DatabaseName": ref("Database"), "TableInput": {
        "Name": "requests_silver", "TableType": "EXTERNAL_TABLE", "PartitionKeys": [{"Name": "dt", "Type": "string"}],
        "Parameters": {"classification": "json", "EXTERNAL": "TRUE", "projection.enabled": "true", "projection.dt.type": "date", "projection.dt.range": "2020-01-01,NOW", "projection.dt.format": "yyyy-MM-dd", "projection.dt.interval": "1", "projection.dt.interval.unit": "DAYS", "storage.location.template": sub("s3://${DataBucket}/silver/dt=${!dt}/")},
        "StorageDescriptor": storage(sub("s3://${DataBucket}/silver/"), columns),
    }})
    r["CommitTable"] = resource("AWS::Glue::Table", {"CatalogId": ref("AWS::AccountId"), "DatabaseName": ref("Database"), "TableInput": {
        "Name": "batch_commits", "TableType": "EXTERNAL_TABLE", "Parameters": {"classification": "json", "EXTERNAL": "TRUE"},
        "StorageDescriptor": storage(sub("s3://${DataBucket}/commits/"), [("batch_id", "string"), ("ingested_at", "string"), ("status", "string"), ("source_rows", "int"), ("accepted", "int"), ("rejected", "int")]),
    }})
    r["AthenaWorkGroup"] = resource("AWS::Athena::WorkGroup", {
        "Name": sub("${AWS::StackName}-analytics"), "RecursiveDeleteOption": True,
        "WorkGroupConfiguration": {"EnforceWorkGroupConfiguration": True, "PublishCloudWatchMetricsEnabled": True, "BytesScannedCutoffPerQuery": 104857600,
            "ResultConfiguration": {"OutputLocation": sub("s3://${DataBucket}/athena-results/"), "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"}}},
    })
    r["FailureMetric"] = resource("AWS::Logs::MetricFilter", {"LogGroupName": ref("WorkerLogGroup"), "FilterPattern": '{ $.kind = "awsflow_failure" }', "MetricTransformations": [{"MetricNamespace": "AWSFlow", "MetricName": sub("${AWS::StackName}-Failures"), "MetricValue": "1", "DefaultValue": 0}]})
    r["FailureAlarm"] = resource("AWS::CloudWatch::Alarm", {"AlarmDescription": "Worker reported a failed SQS item; inspect logs and DLQ", "Namespace": "AWSFlow", "MetricName": sub("${AWS::StackName}-Failures"), "Statistic": "Sum", "Period": 60, "EvaluationPeriods": 1, "Threshold": 1, "ComparisonOperator": "GreaterThanOrEqualToThreshold", "TreatMissingData": "notBreaching"})
    r["QualityMetric"] = resource("AWS::Logs::MetricFilter", {"LogGroupName": ref("WorkerLogGroup"), "FilterPattern": '{ $.kind = "awsflow_batch" && $.status = "blocked_quality_gate" }', "MetricTransformations": [{"MetricNamespace": "AWSFlow", "MetricName": sub("${AWS::StackName}-QualityBlocks"), "MetricValue": "1", "DefaultValue": 0}]})
    r["QualityAlarm"] = resource("AWS::CloudWatch::Alarm", {"AlarmDescription": "Batch quarantined by quality gate; inspect audit/quarantine objects", "Namespace": "AWSFlow", "MetricName": sub("${AWS::StackName}-QualityBlocks"), "Statistic": "Sum", "Period": 60, "EvaluationPeriods": 1, "Threshold": 1, "ComparisonOperator": "GreaterThanOrEqualToThreshold", "TreatMissingData": "notBreaching"})
    r["DlqAlarm"] = resource("AWS::CloudWatch::Alarm", {"AlarmDescription": "Pipeline/event delivery exhausted retries", "Namespace": "AWS/SQS", "MetricName": "ApproximateNumberOfMessagesVisible", "Dimensions": [{"Name": "QueueName", "Value": attr("DeadLetterQueue", "QueueName")}], "Statistic": "Maximum", "Period": 60, "EvaluationPeriods": 1, "Threshold": 1, "ComparisonOperator": "GreaterThanOrEqualToThreshold", "TreatMissingData": "notBreaching"})
    return {
        "AWSTemplateFormatVersion": "2010-09-09", "Description": "AWSFlow: bounded S3/EventBridge/SQS/Lambda data pipeline with Glue catalog and Athena",
        "Parameters": {"ArtifactBucket": {"Type": "String", "Description": "Existing deployment artifact bucket in the same region"}, "ArtifactKey": {"Type": "String", "Description": "Content-addressed Lambda ZIP object key"}, "DatabaseName": {"Type": "String", "Default": "awsflow_demo", "AllowedPattern": "[a-z][a-z0-9_]{0,63}"}},
        "Resources": r,
        "Outputs": {"DataBucket": {"Value": ref("DataBucket")}, "WorkerName": {"Value": ref("Worker")}, "DatabaseName": {"Value": ref("Database")}, "WorkGroupName": {"Value": ref("AthenaWorkGroup")}, "QueueUrl": {"Value": ref("WorkQueue")}, "DeadLetterQueueUrl": {"Value": ref("DeadLetterQueue")}},
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "template.json").write_text(json.dumps(template(), indent=2) + "\n")
    archive = ROOT / "data/awsflow-worker.zip"
    archive.parent.mkdir(exist_ok=True)
    paths = [ROOT / "awsflow/__init__.py", ROOT / "awsflow/worker.py", ROOT / "contractwatch/__init__.py", ROOT / "contractwatch/core.py", ROOT / "contracts/nyc311.json"]
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in paths:
            info = zipfile.ZipInfo(str(path.relative_to(ROOT)), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
    print(OUT / "template.json")
    print(archive)


if __name__ == "__main__":
    main()
