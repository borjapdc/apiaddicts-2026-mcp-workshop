#!/usr/bin/env bash
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf 'Use: source scripts/tools/credentials.sh (sets reader/operator environment keys without printing them)\n'
  exit 0
fi
WORKSHOP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if ! bash "$WORKSHOP_ROOT/scripts/terraform/assert-subscription.sh" >/dev/null; then
  return 2
fi
WORKSHOP_IDS=$(terraform -chdir="$WORKSHOP_ROOT/infra/terraform/gateway" output -json subscription_ids) || return 2
WORKSHOP_READER_ID=$(printf '%s' "$WORKSHOP_IDS" | jq -r .reader)
WORKSHOP_OPERATOR_ID=$(printf '%s' "$WORKSHOP_IDS" | jq -r .operator)
APIM_READER_KEY=$(az rest --method post --url "https://management.azure.com$WORKSHOP_READER_ID/listSecrets?api-version=2025-09-01-preview" --query primaryKey -o tsv --only-show-errors) || return 2
APIM_OPERATOR_KEY=$(az rest --method post --url "https://management.azure.com$WORKSHOP_OPERATOR_ID/listSecrets?api-version=2025-09-01-preview" --query primaryKey -o tsv --only-show-errors) || return 2
export APIM_READER_KEY APIM_OPERATOR_KEY
unset WORKSHOP_IDS WORKSHOP_READER_ID WORKSHOP_OPERATOR_ID
printf 'PASS credentials assigned to environment; no keys printed\n'