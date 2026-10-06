# Project cost policy

User constraint: $0 out-of-pocket project costs. Project creation and verification use local execution, free public data, open-source libraries, and a public GitHub repository with standard hosted CI runners. No paid model APIs, paid datasets, commercial subscriptions, larger GitHub runners, or paid hosting are required by these demos.

No live AWS resources have been deployed by this project work. AWSFlow's historical deployment script now only packages local files; it cannot call AWS or accept deployment options. The CloudFormation template remains reviewable infrastructure code and is not automatically executed. Uploading a template manually in the AWS console can still create resources; that is outside the enabled project workflow.

Do not upgrade the AWS account, activate paid-only services, or initiate cloud usage on the assumption that credits make it free. Before any later live AWS exercise, verify the actual Free account plan, applicable service access, and credit status. AWS credits alone do not establish a $0 out-of-pocket guarantee on a Paid account plan.

GitHub documents standard hosted runners as free for public repositories: https://docs.github.com/en/billing/concepts/product-billing/github-actions . Existing workflows use ubuntu-latest standard runners and no artifact-storage upload steps.

AWS documents no charges on its Free account plan until upgrading: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html . Account plan/status has not been independently inspected here. Local tests and SDK Stubber verification need no AWS account or credentials.

This policy addresses additional project services and resource charges; it does not audit existing subscriptions, internet/electricity, or activity outside this project.
