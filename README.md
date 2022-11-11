# Poll Indents
## Folder Structure
 - ../site - Website front-end
 - ../src - Python back-end

## Google Cloud Authentication
Use following commands to setup Google cloud with service accounts and workflow identity
federation so that the Github actions can directly deploy from the repository.

```bash

#### DEFINE VARIABLES ####
# update all variables here to match your requirements
export PROJECT_ID="mp-indents-01"
export RUNTIME_ACCOUNT="functions-runtime-02"
export SERVICE_ACCOUNT_NAME="github-service-02"
export POOL_NAME="github-pool-02"
export PROVIDER_NAME="github-token-provider-02"
export REPO_NAME="mpette200/poll-indents"

# The variable REPO_NAME is used to set a condition requiring
# the repository name in the JSON web token to match the value
# defined here. This is a way of ensuring that only workflows
# from this specific repository will be granted permission.

#### END OF VARIABLES ####

gcloud config set project "${PROJECT_ID}"

gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}"

gcloud iam service-accounts create "${RUNTIME_ACCOUNT}"

gcloud services enable iamcredentials.googleapis.com

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role='roles/cloudfunctions.admin'

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role='roles/datastore.owner'

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role='roles/datastore.owner'

gcloud iam service-accounts add-iam-policy-binding \
    "${RUNTIME_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role='roles/iam.serviceAccountUser'

gcloud iam workload-identity-pools create "${POOL_NAME}" \
  --location="global"

# Important for security: --attribute-condition
gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_NAME}" \
  --location="global" \
  --workload-identity-pool="${POOL_NAME}" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner_id=assertion.repository_owner_id" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-condition="attribute.repository_owner_id=='19962594'"

# save this for next command
export POOL_ID_LONG="$( \
    gcloud iam workload-identity-pools describe "${POOL_NAME}" \
    --location="global" \
    --format="value(name)" \
)"
# Important for security:
# .../attribute.repository/${REPO_NAME}
# allows access only from the specific repository
gcloud iam service-accounts add-iam-policy-binding \
  "${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID_LONG}/attribute.repository/${REPO_NAME}"

# use this value as the workload_identity_provider in your Github Actions YAML
gcloud iam workload-identity-pools providers describe "${PROVIDER_NAME}" \
  --location="global" \
  --workload-identity-pool="${POOL_NAME}" \
  --format="value(name)"

```
