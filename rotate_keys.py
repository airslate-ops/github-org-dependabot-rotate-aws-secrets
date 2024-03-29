import boto3, requests, json, sys, os
from base64 import b64encode
from nacl import encoding, public

# sets default value
access_key_name = "access_key_id"
secret_key_name = "secret_key_id"

# checks if values set to override default
if 'GITHUB_ACCESS_KEY_NAME' in os.environ:
    access_key_name = os.environ['GITHUB_ACCESS_KEY_NAME']

if 'GITHUB_SECRET_KEY_NAME' in os.environ:
    secret_key_name = os.environ['GITHUB_SECRET_KEY_NAME']

# sets creds for boto3
iam = boto3.client(
    'iam',
    aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY'],
    aws_session_token = os.environ['AWS_SESSION_TOKEN'] if 'AWS_SESSION_TOKEN' in os.environ else None
)

def main_function():
    iam_username = os.environ['IAM_USERNAME'] if 'IAM_USERNAME' in os.environ else who_am_i()
    github_token = os.environ['PERSONAL_ACCESS_TOKEN']
    owner_organization = os.environ['OWNER_ORGANIZATION']
    owner_repository = os.environ['OWNER_REPOSITORY']

    list_ret = iam.list_access_keys(UserName=iam_username)
    starting_num_keys = len(list_ret["AccessKeyMetadata"])

    # save current id for deletion later
    current_access_id = list_ret["AccessKeyMetadata"][0]["AccessKeyId"]

    # Check if two keys already exist, if so, exit 1
    if starting_num_keys != 1:
        print("There are already 2 keys for this user, Cannot rotate tokens")
        sys.exit(1)
    else:
        print(f"I have {starting_num_keys} token, proceeding.")

    #generate new credentials
    (new_access_key, new_secret_key) = create_new_keys(iam_username)

    #get org pub key info
    (dependabot_public_key, dependabot_pub_key_id) = get_dependabot_pub_key(owner_organization, github_token)
    (repo_public_key, repo_pub_key_id) = get_repo_pub_key(owner_repository, github_token)

    #encrypt the secrets
    repo_encrypted_access_key = encrypt(repo_public_key,new_access_key)
    repo_encrypted_secret_key = encrypt(repo_public_key,new_secret_key)
    dependabot_encrypted_access_key = encrypt(dependabot_public_key,new_access_key)
    dependabot_encrypted_secret_key = encrypt(dependabot_public_key,new_secret_key)

    #upload secrets
    upload_repo_secret(owner_repository,access_key_name,repo_encrypted_access_key,repo_pub_key_id,github_token)
    upload_repo_secret(owner_repository,secret_key_name,repo_encrypted_secret_key,repo_pub_key_id,github_token)
    upload_dependabot_secret(owner_organization,access_key_name,dependabot_encrypted_access_key,dependabot_pub_key_id,github_token)
    upload_dependabot_secret(owner_organization,secret_key_name,dependabot_encrypted_secret_key,dependabot_pub_key_id,github_token)

    #delete old keys
    delete_old_keys(iam_username, current_access_id)

    sys.exit(0)

def who_am_i():
    # ask the aws backend for myself with a boto3 sts client
    sts = boto3.client(
        'sts',
        aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY'],
        aws_session_token = os.environ['AWS_SESSION_TOKEN'] if 'AWS_SESSION_TOKEN' in os.environ else None
    )

    user = sts.get_caller_identity()
    # return last element of splitted list to get username
    return user['Arn'].split("/")[-1]

def create_new_keys(iam_username):
    # create the keys
    create_ret = iam.create_access_key(
            UserName=iam_username
        )

    new_access_key = create_ret['AccessKey']['AccessKeyId']
    new_secret_key = create_ret['AccessKey']['SecretAccessKey']

    # check to see if the keys were created
    second_list_ret = iam.list_access_keys(UserName=iam_username)
    second_num_keys = len(second_list_ret["AccessKeyMetadata"])

    if second_num_keys != 2:
        print("new keys failed to generate.")
        sys.exit(1)
    else:
        print("new keys generated, proceeding")
        return (new_access_key,new_secret_key)

def delete_old_keys(iam_username,current_access_id):
    delete_ret = iam.delete_access_key(
            UserName=iam_username,
            AccessKeyId=current_access_id
        )

    if delete_ret['ResponseMetadata']['HTTPStatusCode'] != 200:
        print("deletion of original key failed")
        sys.exit(1)

## Update Dependabot Secret
# https://docs.github.com/en/rest/dependabot/secrets#create-or-update-an-organization-secret
def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")

def get_dependabot_pub_key(owner_org, github_token):
    # get public key for encrypting
    pub_key_ret = requests.get(
        f'https://api.github.com/orgs/{owner_org}/dependabot/secrets/public-key',
        headers={'Authorization': f"token {github_token}"}
    )

    if not pub_key_ret.status_code == requests.codes.ok:
        raise Exception(f"github public key request failed, status code: {pub_key_ret.status_code}, body: {pub_key_ret.text}, vars: {owner_org} {github_token}")
        sys.exit(1)

    #convert to json
    public_key_info = pub_key_ret.json()

    #extract values
    public_key = public_key_info['key']
    public_key_id = public_key_info['key_id']

    return (public_key, public_key_id)

def upload_dependabot_secret(owner_org,key_name,encrypted_value,pub_key_id,github_token):
    #upload encrypted access key
    updated_secret = requests.put(
        f'https://api.github.com/orgs/{owner_org}/dependabot/secrets/{key_name}',
        json={
            'encrypted_value': encrypted_value,
            'key_id': pub_key_id,
            'visibility': f"private"
        },
        headers={'Authorization': f"token {github_token}"}
    )
    # status codes github says are valid
    good_status_codes = [204,201]

    if updated_secret.status_code not in good_status_codes:
        print(f'Got status code: {updated_secret.status_code} on updating {key_name} in {owner_org}')
        sys.exit(1)
    print(f'Updated {key_name} in {owner_org}')

# Update Repository Secret, because: Gets a single organization secret without revealing its encrypted value.
# https://docs.github.com/en/rest/dependabot/secrets#get-an-organization-secret
def get_repo_pub_key(owner_repo, github_token):
    # get public key for encrypting
    pub_key_ret = requests.get(
        f'https://api.github.com/repos/{owner_repo}/actions/secrets/public-key',
        headers={'Authorization': f"token {github_token}"}
    )

    if not pub_key_ret.status_code == requests.codes.ok:
        raise Exception(f"github public key request failed, status code: {pub_key_ret.status_code}, body: {pub_key_ret.text}, vars: {owner_repo} {github_token}")
        sys.exit(1)

    #convert to json
    public_key_info = pub_key_ret.json()

    #extract values
    public_key = public_key_info['key']
    public_key_id = public_key_info['key_id']

    return (public_key, public_key_id)

def upload_repo_secret(owner_repo,key_name,encrypted_value,pub_key_id,github_token):
    #upload encrypted access key
    updated_secret = requests.put(
        f'https://api.github.com/repos/{owner_repo}/actions/secrets/{key_name}',
        json={
            'encrypted_value': encrypted_value,
            'key_id': pub_key_id
        },
        headers={'Authorization': f"token {github_token}"}
    )
    # status codes github says are valid
    good_status_codes = [204,201]

    if updated_secret.status_code not in good_status_codes:
        print(f'Got status code: {updated_secret.status_code} on updating {key_name} in {owner_repo}')
        sys.exit(1)
    print(f'Updated {key_name} in {owner_repo}')

# run everything
main_function()
