# Rotate AWS Access token stored in Github Organizations dependabot scope secrets

Version for rotate organization secret, cloned from [kneemaa/github-action-rotate-aws-secrets](https://github.com/kneemaa/github-action-rotate-aws-secrets)

#### Maintainer Dmitry Teikovtsev <teikovtsev.dmitry@pdffiller.team>

## Note:
- secret **visibility** only **private** - Private repositories in an organization can access. May be later add visibility for **all** and **selected** variant

## Environment Variables
#### AWS_ACCESS_KEY_ID
- Required: ***True***
- Description: Access Key ID to authenticate with AWS. You can use `${{secrets.ACCESS_KEY_ID}}`
- Should be in organization secrets

#### AWS_SECRET_ACCESS_KEY
- Required: ***True***
- Description: Secret Access Key ID to authenticate with AWS. You can use `${{secrets.SECRET_ACCESS_KEY_ID}}`
- Should be in organization secrets

#### AWS_SESSION_TOKEN
- Required: ***False***
- Description: Session Token for the current AWS session. Only required if you assume a role first.
- Should be in organization secrets

#### IAM_USERNAME
- Required: ***False***
- Description: Name of IAM user being rotated, if not set the username which is used in the AWS credentials is used
- Can be in repository secrets or in organization secrets or plaintext

#### PERSONAL_ACCESS_TOKEN
- Required: ***True***
- Description: Github Token with **Repo Admin** access of the target repo. As of 4/16/2020 `${{github.token}}` does not have permission to query the Secrets API. The existing env var GITHUB_TOKEN which is added automatically to all runs does not have the access secrets.
- Can be in repository secrets or in organization secrets

#### OWNER_ORGANIZATION
- Required: ***True***
- Description: The owner repository name. For example, octocat. If being ran in the repo being updated, you can use `${{github.repository_owner}}`

#### OWNER_REPOSITORY
- Required: ***True***
- Description: The repository name. For example, octocat. If being ran in the repo being updated, you can use `${{github.repository}}`

#### GITHUB_ACCESS_KEY_NAME
- Required: ***False***
- Default: `access_key_id`
- Description: Name of the secret for the Access Key ID. Setting this overrides the default.
- Can be in repository secrets or in organization secrets or plaintext

#### GITHUB_SECRET_KEY_NAME
- Required: ***False***
- Default: `secret_key_id`
- Description: Name of the secret for the Secret Access Key ID. Setting this overrides the default.
- Can be in repository secrets or in organization secrets or plaintext

# Example
## Rotation every monday at 13:00 UTC
```
on:
  schedule:
    - cron: '* 13 * * 1'

jobs:
  rotate:
    name: rotate iam user keys
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2.0.0

      - name: rotate aws keys
        uses: airslate-ops/github-org-dependabot-rotate-aws-secrets@v0.1.0
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.access_key_name }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.secret_key_name }}
          IAM_USERNAME: 'iam-user-name'
          PERSONAL_ACCESS_TOKEN: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
          OWNER_ORGANIZATION: ${{ github.repository_owner }}
          OWNER_REPOSITORY: {{ github.repository }}
```

## Adding Slack notification on failure only
```
on:
  schedule:
    - cron: '* 13 * * 1'

jobs:
  rotate:
    name: rotate iam user keys
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2.0.0

      - name: rotate aws keys
        uses: airslate-ops/github-org-dependabot-rotate-aws-secrets@v0.1.0
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.access_key_name }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.secret_key_name }}
          IAM_USERNAME: 'iam-user-name'
          PERSONAL_ACCESS_TOKEN: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
          OWNER_ORGANIZATION: ${{ github.repository_owner }}
          OWNER_REPOSITORY: {{ github.repository }}

      - name: Send Slack Status
        if: failure()
        uses: 8398a7/action-slack@v2.7.0
        with:
          status: ${{job.status}}
          author_name: kneemaa-aws-rotation-action
          username: kneemaa-rotation-bot
          text: Rotating the token had a status of ${{ job.status }}
          channel: alerts-test
        env:
          SLACK_WEBHOOK_URL: https://hooks.slack.com/services/.../...
```
## License
The Dockerfile and associated scripts and documentation in this project are released under the [MIT License](LICENSE).
